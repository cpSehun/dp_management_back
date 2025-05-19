from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
import json
import os
import asyncio
import logging
from urllib import request
from app.security import get_current_user
from app.schemas import User

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ComfyUI 서버 IP 및 포트
COMFYUI_IP = os.getenv("COMFYUI_SERVER", "127.0.0.1:8188")
logger.info(f"ComfyUI 서버 주소: {COMFYUI_IP}")

# Flux 워크플로우 JSON 파일 경로
FLUX_WORKFLOW_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "flux_workflow.json")
logger.info(f"Flux 워크플로우 경로: {FLUX_WORKFLOW_PATH}")

# ComfyUI에서 지원하지 않는 노드 타입 목록
UNSUPPORTED_NODE_TYPES = [
    "PrimitiveNode",  # 원시 데이터 노드 (ComfyUI에서 지원 안 함)
    "Note",           # 메모 노드 (ComfyUI에서 지원 안 함)
    "Reroute",        # 재라우팅 노드 (시각적 요소)
]

router = APIRouter()

class PromptRequest(BaseModel):
    prompt: str
    steps: Optional[int] = Field(default=40, ge=1, le=100)
    cfg_scale: Optional[float] = Field(default=7.0, ge=1.0, le=30.0)
    seed: Optional[int] = None
    batch_size: Optional[int] = Field(default=1, ge=1, le=4)  # 배치 크기: 생성할 이미지 갯수

def load_flux_workflow():
    """Flux 워크플로우 JSON 파일 로드"""
    try:
        # 파일 존재 여부 먼저 확인
        if not os.path.exists(FLUX_WORKFLOW_PATH):
            logger.warning(f"Flux 워크플로우 파일이 존재하지 않습니다: {FLUX_WORKFLOW_PATH}")
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {FLUX_WORKFLOW_PATH}")
            
        with open(FLUX_WORKFLOW_PATH, 'r') as f:
            data = json.load(f)
            logger.info(f"Flux 워크플로우 로드 성공. 키: {', '.join(data.keys())}")
            
            # 워크플로우의 모든 노드 로깅
            if "nodes" in data:
                logger.info(f"워크플로우에서 {len(data['nodes'])}개의 노드 발견")
                for node in data["nodes"]:
                    node_id = node.get("id", "알 수 없음")
                    node_type = node.get("class_type", node.get("type", "알 수 없음"))
                    node_title = node.get("title", "제목 없음")
                    logger.info(f"노드 ID: {node_id}, 유형: {node_type}, 제목: {node_title}")
            
            return data
    except Exception as e:
        logger.error(f"Flux 워크플로우 JSON 파일을 로드할 수 없습니다: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Flux 워크플로우 JSON 파일을 로드할 수 없습니다: {str(e)}")

def modify_workflow_with_prompt(workflow, request: PromptRequest):
    """사용자 프롬프트로 워크플로우 수정"""
    # 노드 ID가 하드코딩되어 있지만, 실제 워크플로우에서 노드 클래스 타입으로 찾기
    clip_text_encode_found = False
    width_node_found = False
    height_node_found = False
    noise_node_found = False
    scheduler_node_found = False
    batch_size_node_found = False
    save_image_fixed = False
    
    # SaveImage 노드 연결 정보 확인을 위한 변수 초기화
    save_image_nodes = []
    save_image_connections = {}
    
    # 노드 유형별 ID 저장 (링크 자동 생성에 사용)
    node_type_ids = {
        "CLIPTextEncode": [],
        "UNETLoader": [],
        "VAELoader": [],
        "VAEDecode": [],
        "SaveImage": [],
        "RandomNoise": [],
        "EmptySD3LatentImage": [],
        "EmptyLatentImage": [],
        "KSamplerSelect": [],
        "SamplerCustomAdvanced": [],
        "BasicScheduler": [],
        "DualCLIPLoader": []
    }
    
    # SaveImage 노드 찾기
    for node in workflow["nodes"]:
        node_type = node.get("class_type", node.get("type", "unknown"))
        node_id = node.get("id", "unknown")
        
        # 노드 유형별로 ID 저장
        if node_type in node_type_ids:
            node_type_ids[node_type].append(str(node_id))
        
        if node_type == "SaveImage":
            save_image_nodes.append(node)
            
    logger.info(f"워크플로우에서 {len(save_image_nodes)}개의 SaveImage 노드를 찾았습니다")
    
    # SaveImage 노드 연결 정보 확인
    if "links" in workflow:
        for link in workflow["links"]:
            if len(link) >= 4:
                target_id = str(link[2])
                for node in save_image_nodes:
                    if str(node.get("id")) == target_id:
                        # SaveImage로 들어오는 연결 저장
                        if target_id not in save_image_connections:
                            save_image_connections[target_id] = []
                        save_image_connections[target_id].append(link)
    
    # 노드 유형을 기준으로 찾기
    logger.info(f"워크플로우 수정 시작: 프롬프트='{request.prompt[:30]}...', 배치 크기={request.batch_size}")
    
    # CLIPTextEncode 노드 리스트 확인 (디버깅용)
    clip_nodes = []
    for node in workflow["nodes"]:
        if "class_type" in node and node["class_type"] == "CLIPTextEncode":
            clip_nodes.append({
                "id": node.get("id"),
                "title": node.get("title", "제목 없음"),
                "has_widgets_values": "widgets_values" in node,
                "has_inputs_text": "inputs" in node and "text" in node.get("inputs", {})
            })
    
    # 워크플로우의 모든 CLIPTextEncode 노드 로깅
    if clip_nodes:
        logger.info(f"워크플로우에서 {len(clip_nodes)}개의 CLIPTextEncode 노드 발견:")
        for idx, node in enumerate(clip_nodes):
            logger.info(f"  {idx+1}. ID: {node['id']}, 제목: {node['title']}, widgets_values: {node['has_widgets_values']}, inputs.text: {node['has_inputs_text']}")
    else:
        logger.warning("워크플로우에서 CLIPTextEncode 노드를 찾을 수 없습니다.")
    
    # 노드 유형별로 찾기 전에 지원되지 않는 노드 필터링
    filtered_nodes = []
    unsupported_types = []
    kept_node_ids = set()  # 유지되는 노드 ID 집합
    
    for node in workflow["nodes"]:
        node_type = node.get("class_type", node.get("type", "unknown"))
        node_id = node.get("id", "unknown")
        
        if node_type in UNSUPPORTED_NODE_TYPES:
            # 지원되지 않는 노드 타입
            unsupported_types.append(f"{node_type} (ID: {node_id})")
            continue
            
        filtered_nodes.append(node)
        kept_node_ids.add(str(node_id))  # ID를 문자열로 저장
    
    if unsupported_types:
        logger.warning(f"지원되지 않는 노드 유형 {len(unsupported_types)}개를 제거했습니다: {', '.join(unsupported_types)}")
    
    # 필터링된 노드로 워크플로우 업데이트
    workflow["nodes"] = filtered_nodes
    
    # Links 정보도 업데이트
    if "links" in workflow:
        filtered_links = []
        original_links_count = len(workflow["links"])
        
        for link in workflow["links"]:
            # 링크는 [원본_ID, 출력_슬롯, 대상_ID, 입력_슬롯] 형식으로 구성됨
            if len(link) >= 4:
                source_id = str(link[0])
                target_id = str(link[2])
                
                if source_id in kept_node_ids and target_id in kept_node_ids:
                    filtered_links.append(link)
        
        workflow["links"] = filtered_links
        logger.info(f"links 정보 업데이트: {original_links_count}개 중 {len(filtered_links)}개 유지")
    
    # 노드 유형별로 찾기
    for node in workflow["nodes"]:
        node_type = node.get("class_type", node.get("type", "unknown"))
        node_id = node.get("id", "unknown")
        
        # 1. CLIPTextEncode 노드 (프롬프트 입력)
        if node_type == "CLIPTextEncode":
            # 프롬프트 입력을 위한 CLIP Text Encode 노드 찾음
            if "title" in node and "Positive Prompt" in node.get("title", ""):
                # 포지티브 프롬프트 노드 (특별히 표시된 경우)
                logger.info(f"포지티브 프롬프트 노드 찾음 (ID: {node_id})")
                if "widgets_values" in node:
                    node["widgets_values"][0] = request.prompt
                    clip_text_encode_found = True
                    logger.info(f"포지티브 프롬프트 노드 업데이트: {request.prompt[:30]}...")
                elif "inputs" in node and "text" in node["inputs"]:
                    node["inputs"]["text"] = request.prompt
                    clip_text_encode_found = True
                    logger.info(f"포지티브 프롬프트 노드 inputs.text 업데이트: {request.prompt[:30]}...")
            elif not clip_text_encode_found:
                # 첫 번째 CLIPTextEncode 노드를 포지티브 프롬프트로 사용
                logger.info(f"첫 번째 CLIPTextEncode 노드를 포지티브 프롬프트로 사용 (ID: {node_id})")
                if "widgets_values" in node:
                    node["widgets_values"][0] = request.prompt
                    clip_text_encode_found = True
                    logger.info(f"CLIPTextEncode 노드 프롬프트 업데이트: {request.prompt[:30]}...")
                elif "inputs" in node and "text" in node["inputs"]:
                    node["inputs"]["text"] = request.prompt
                    clip_text_encode_found = True
                    logger.info(f"CLIPTextEncode 노드 inputs.text 업데이트: {request.prompt[:30]}...")
        
        # 2. EmptyLatentImage 또는 EmptySD3LatentImage 노드 (너비, 높이, 배치 크기)
        elif node_type in ["EmptyLatentImage", "EmptySD3LatentImage"]:
            logger.info(f"{node_type} 노드 찾음 (ID: {node_id})")
            
            # 배치 크기 설정
            batch_found = False
            
            # widgets_values로 설정
            if "widgets_values" in node:
                # 배치 크기 (일반적으로 세 번째 값)
                if len(node["widgets_values"]) > 2:
                    node["widgets_values"][2] = request.batch_size
                    batch_found = True
                    batch_size_node_found = True
                    logger.info(f"{node_type} 배치 크기 업데이트: {request.batch_size}")
            
            # inputs로 설정
            if "inputs" in node:
                # inputs가 딕셔너리인 경우
                if isinstance(node["inputs"], dict):
                    if "batch_size" in node["inputs"] and not batch_found:
                        node["inputs"]["batch_size"] = request.batch_size
                        batch_size_node_found = True
                        logger.info(f"{node_type} inputs.batch_size 업데이트: {request.batch_size}")
        
        # 4. KSampler 또는 유사한 노드 (시드, 스텝 수)
        elif node_type in ["KSampler", "SamplerCustom", "SamplerCustomAdvanced"]:
            logger.info(f"{node_type} 노드 찾음 (ID: {node_id})")
            
            seed_found = False
            steps_found = False
            
            # widgets_values로 설정
            if "widgets_values" in node:
                # 대부분의 KSampler는 첫 번째 값이 시드
                if len(node["widgets_values"]) > 0 and request.seed is not None:
                    node["widgets_values"][0] = request.seed
                    seed_found = True
                    noise_node_found = True
                    logger.info(f"{node_type} 시드 업데이트: {request.seed}")
                
                # 스텝 수는 보통 두 번째 또는 세 번째 값
                if len(node["widgets_values"]) > 1:
                    # 경험적으로 볼 때 두 번째 값이 스텝인 경우가 많음
                    node["widgets_values"][1] = request.steps
                    steps_found = True
                    scheduler_node_found = True
                    logger.info(f"{node_type} 스텝 업데이트: {request.steps}")
            
            # inputs로 설정
            if "inputs" in node:
                if isinstance(node["inputs"], dict):
                    if "seed" in node["inputs"] and request.seed is not None and not seed_found:
                        node["inputs"]["seed"] = request.seed
                        noise_node_found = True
                        logger.info(f"{node_type} inputs.seed 업데이트: {request.seed}")
                    
                    if "steps" in node["inputs"] and not steps_found:
                        node["inputs"]["steps"] = request.steps
                        scheduler_node_found = True
                        logger.info(f"{node_type} inputs.steps 업데이트: {request.steps}")
        
        # 5. RandomNoise 노드 (시드)
        elif node_type == "RandomNoise":
            logger.info(f"RandomNoise 노드 찾음 (ID: {node_id})")
            
            if "widgets_values" in node and len(node["widgets_values"]) > 0 and request.seed is not None:
                node["widgets_values"][0] = request.seed
                noise_node_found = True
                logger.info(f"RandomNoise 시드 업데이트: {request.seed}")
                
                # 시드 모드 설정 (있을 경우)
                if len(node["widgets_values"]) > 1:
                    node["widgets_values"][1] = "fixed"
                    logger.info("RandomNoise 시드 모드를 'fixed'로 설정")
        
        # 6. SaveImage 노드 (파일명 접두어 확인)
        elif node_type == "SaveImage":
            logger.info(f"SaveImage 노드 찾음 (ID: {node_id})")
            
            # inputs 키 확인 및 생성
            if "inputs" not in node:
                # inputs가 없으면 빈 딕셔너리로 생성
                node["inputs"] = {}
                logger.info(f"SaveImage 노드 ID {node_id}에 inputs 키 추가")
            
            # inputs의 타입 확인
            if isinstance(node["inputs"], list):
                # 리스트 형태의 inputs는 ComfyUI와 호환되지 않을 수 있음
                logger.warning(f"SaveImage 노드 ID {node_id}의 inputs가 리스트 형태입니다. 딕셔너리로 변환합니다.")
                # 리스트를 딕셔너리로 변환 시도
                try:
                    # 기존 리스트 값 보존
                    original_inputs = node["inputs"]
                    # 새로운 딕셔너리 생성
                    new_inputs = {}
                    
                    # VAEDecode 노드 찾기
                    vae_decode_nodes = []
                    for other_node in workflow["nodes"]:
                        other_type = other_node.get("class_type", other_node.get("type", "unknown"))
                        if other_type in ["VAEDecode", "VaeDecoder"]:
                            vae_decode_nodes.append(other_node)
                    
                    # images 입력 설정
                    if vae_decode_nodes:
                        vae_node = vae_decode_nodes[0]
                        vae_node_id = vae_node.get("id", "unknown")
                        new_inputs["images"] = [vae_node_id, 0]
                        logger.info(f"SaveImage 노드 ID {node_id}에 VAEDecode 노드 연결: {vae_node_id}")
                    else:
                        # 연결 정보에서 찾기
                        if str(node_id) in save_image_connections and save_image_connections[str(node_id)]:
                            link = save_image_connections[str(node_id)][0]
                            source_id = link[0]
                            output_slot = link[1]
                            new_inputs["images"] = [source_id, output_slot]
                            logger.info(f"SaveImage 노드 ID {node_id}에 링크 연결 발견: [{source_id}, {output_slot}]")
                    
                    # filename_prefix 설정
                    new_inputs["filename_prefix"] = "ComfyUI"
                    
                    # 새로운 inputs로 교체
                    node["inputs"] = new_inputs
                    logger.info(f"SaveImage 노드 ID {node_id}의 inputs를 딕셔너리로 변환 완료")
                except Exception as e:
                    logger.error(f"SaveImage 노드 ID {node_id}의 inputs 변환 중 오류 발생: {str(e)}")
                    # 오류 시 기본값으로 재설정
                    node["inputs"] = {"filename_prefix": "ComfyUI"}
            
            # 이제 inputs는 딕셔너리 형태여야 함
            if isinstance(node["inputs"], dict):
                # filename_prefix 필드 확인 및 추가
                if "filename_prefix" not in node["inputs"]:
                    node["inputs"]["filename_prefix"] = "ComfyUI"
                    logger.info(f"SaveImage 노드 ID {node_id}에 filename_prefix 입력 추가")
                
                # images 필드 연결 확인
                if "images" not in node["inputs"]:
                    # 연결 정보에서 images 입력 찾기
                    if str(node_id) in save_image_connections and save_image_connections[str(node_id)]:
                        # 첫 번째 연결 사용
                        link = save_image_connections[str(node_id)][0]
                        # [source_id, output_slot, target_id, input_slot]
                        source_id = link[0]
                        output_slot = link[1]
                        node["inputs"]["images"] = [source_id, output_slot]
                        logger.info(f"SaveImage 노드 ID {node_id}에 links 정보로부터 images 입력 연결: [{source_id}, {output_slot}]")
                    else:
                        # 다른 노드 찾기 (VAEDecode 또는 이미지 출력 노드)
                        vae_decode_nodes = []
                        for other_node in workflow["nodes"]:
                            other_type = other_node.get("class_type", other_node.get("type", "unknown"))
                            if other_type in ["VAEDecode", "VaeDecoder"]:
                                vae_decode_nodes.append(other_node)
                        
                        if vae_decode_nodes:
                            # 첫 번째 VAEDecode 노드 사용
                            vae_node = vae_decode_nodes[0]
                            vae_node_id = vae_node.get("id", "unknown")
                            node["inputs"]["images"] = [vae_node_id, 0]  # 대부분 0번 출력이 이미지
                            logger.info(f"SaveImage 노드 ID {node_id}에 VAEDecode 노드 ID {vae_node_id}로 images 입력 연결")
                        else:
                            logger.warning(f"SaveImage 노드 ID {node_id}에 images 입력을 연결할 노드를 찾지 못했습니다")
            
            save_image_fixed = True
    
    if save_image_fixed:
        logger.info("SaveImage 노드 수정 완료")
    
    # 프롬프트 노드를 찾지 못한 경우 경고
    if not clip_text_encode_found:
        logger.warning("CLIPTextEncode 노드를 찾을 수 없어 프롬프트를 적용할 수 없습니다.")
    
    # 배치 크기 노드를 찾지 못한 경우 경고
    if not batch_size_node_found:
        logger.warning("EmptyLatentImage/EmptySD3LatentImage 노드를 찾을 수 없어 배치 크기를 적용할 수 없습니다.")
    
    logger.info(f"워크플로우 수정 완료: 프롬프트={clip_text_encode_found}, 너비={width_node_found}, 높이={height_node_found}, 시드={noise_node_found}, 스텝={scheduler_node_found}, 배치 크기={batch_size_node_found}")
    
    # 링크 정보 복원 - 노드 유형 별 아이디 수집
    node_type_ids = {}
    
    # 모든 노드 탐색하여 타입별 ID 수집
    for node in workflow["nodes"]:
        node_type = node.get("class_type", node.get("type", "unknown"))
        node_id = str(node.get("id", "unknown"))
        
        if node_type not in node_type_ids:
            node_type_ids[node_type] = []
            
        node_type_ids[node_type].append(node_id)
    
    # 링크 정보가 비어있을 경우 기본 링크 생성
    if not workflow.get("links", []):
        logger.warning("워크플로우에 링크가 없습니다. 기본 링크를 생성합니다.")
        new_links = []
        
        # VAEDecode -> SaveImage 연결은 필수
        if "VAEDecode" in node_type_ids and "SaveImage" in node_type_ids and node_type_ids["VAEDecode"] and node_type_ids["SaveImage"]:
            new_links.append([
                int(node_type_ids["VAEDecode"][0]), 0,  # source: VAEDecode, output slot 0
                int(node_type_ids["SaveImage"][0]), 0   # target: SaveImage, input slot 0
            ])
            logger.info(f"필수 링크 생성: VAEDecode -> SaveImage")
        
        # SamplerCustomAdvanced -> VAEDecode 연결
        if "SamplerCustomAdvanced" in node_type_ids and "VAEDecode" in node_type_ids and node_type_ids["SamplerCustomAdvanced"] and node_type_ids["VAEDecode"]:
            new_links.append([
                int(node_type_ids["SamplerCustomAdvanced"][0]), 0,
                int(node_type_ids["VAEDecode"][0]), 0
            ])
            logger.info(f"링크 생성: SamplerCustomAdvanced -> VAEDecode")
        
        # VAELoader -> VAEDecode 연결
        if "VAELoader" in node_type_ids and "VAEDecode" in node_type_ids and node_type_ids["VAELoader"] and node_type_ids["VAEDecode"]:
            new_links.append([
                int(node_type_ids["VAELoader"][0]), 0,
                int(node_type_ids["VAEDecode"][0]), 1
            ])
            logger.info(f"링크 생성: VAELoader -> VAEDecode")
        
        # CLIPTextEncode -> SamplerCustomAdvanced 연결
        if "CLIPTextEncode" in node_type_ids and "SamplerCustomAdvanced" in node_type_ids and node_type_ids["CLIPTextEncode"] and node_type_ids["SamplerCustomAdvanced"]:
            new_links.append([
                int(node_type_ids["CLIPTextEncode"][0]), 0,
                int(node_type_ids["SamplerCustomAdvanced"][0]), 1
            ])
            logger.info(f"링크 생성: CLIPTextEncode -> SamplerCustomAdvanced")
        
        # EmptySD3LatentImage -> SamplerCustomAdvanced 연결
        if "EmptySD3LatentImage" in node_type_ids and "SamplerCustomAdvanced" in node_type_ids and node_type_ids["EmptySD3LatentImage"] and node_type_ids["SamplerCustomAdvanced"]:
            new_links.append([
                int(node_type_ids["EmptySD3LatentImage"][0]), 0,
                int(node_type_ids["SamplerCustomAdvanced"][0]), 3
            ])
            logger.info(f"링크 생성: EmptySD3LatentImage -> SamplerCustomAdvanced")
        
        # RandomNoise -> SamplerCustomAdvanced 연결
        if "RandomNoise" in node_type_ids and "SamplerCustomAdvanced" in node_type_ids and node_type_ids["RandomNoise"] and node_type_ids["SamplerCustomAdvanced"]:
            new_links.append([
                int(node_type_ids["RandomNoise"][0]), 0,
                int(node_type_ids["SamplerCustomAdvanced"][0]), 2
            ])
            logger.info(f"링크 생성: RandomNoise -> SamplerCustomAdvanced")
        
        # UNETLoader -> SamplerCustomAdvanced 연결
        if "UNETLoader" in node_type_ids and "SamplerCustomAdvanced" in node_type_ids and node_type_ids["UNETLoader"] and node_type_ids["SamplerCustomAdvanced"]:
            new_links.append([
                int(node_type_ids["UNETLoader"][0]), 0,
                int(node_type_ids["SamplerCustomAdvanced"][0]), 0
            ])
            logger.info(f"링크 생성: UNETLoader -> SamplerCustomAdvanced")
        
        # 링크 설정
        workflow["links"] = new_links
        logger.info(f"{len(new_links)}개의 기본 링크를 생성했습니다")
    
    return workflow

def queue_prompt(workflow, ip, client_id="dp_management"):
    """ComfyUI API로 프롬프트 전송"""
    # 워크플로우를 적절한 형태로 정리 (ComfyUI API 요구사항)
    # ComfyUI의 서버 구현에 맞게 데이터 형식 수정
    
    logger.info("ComfyUI 프롬프트 데이터 준비 시작")
    
    try:
        # 워크플로우 구조 검증
        if not isinstance(workflow, dict):
            logger.error(f"워크플로우가 딕셔너리 형식이 아닙니다: {type(workflow)}")
            raise HTTPException(status_code=500, detail="워크플로우 형식 오류")
        
        if "nodes" not in workflow or not isinstance(workflow["nodes"], list):
            logger.error("워크플로우에 'nodes' 리스트가 없습니다")
            raise HTTPException(status_code=500, detail="워크플로우 형식 오류: 'nodes' 리스트 없음")
        
        if len(workflow["nodes"]) == 0:
            logger.error("워크플로우에 노드가 없습니다")
            raise HTTPException(status_code=500, detail="워크플로우 형식 오류: 노드가 없음")
        
        # 주요 노드 유형 식별
        vae_decode_nodes = []
        save_image_nodes = []
        
        for node in workflow["nodes"]:
            node_type = node.get("class_type", node.get("type", "unknown"))
            node_id = node.get("id", "unknown")
            
            if node_type in ["VAEDecode", "VaeDecoder"]:
                vae_decode_nodes.append((node_id, node))
                logger.info(f"VAEDecode 노드 발견: ID={node_id}")
            
            if node_type == "SaveImage":
                save_image_nodes.append((node_id, node))
                logger.info(f"SaveImage 노드 발견: ID={node_id}")
        
        if not vae_decode_nodes:
            logger.warning("VAEDecode 노드를 찾을 수 없습니다. 이미지 생성이 불가능할 수 있습니다.")
        
        if not save_image_nodes:
            logger.warning("SaveImage 노드를 찾을 수 없습니다. 이미지가 저장되지 않을 수 있습니다.")
        
        # SaveImage 노드가 있고 VAEDecode 노드가 있으면 연결 확인
        if save_image_nodes and vae_decode_nodes:
            for save_id, save_node in save_image_nodes:
                if "inputs" not in save_node or not isinstance(save_node["inputs"], dict):
                    save_node["inputs"] = {}
                
                # images 입력이 없으면 VAEDecode 연결
                if "images" not in save_node["inputs"]:
                    vae_id = vae_decode_nodes[0][0]  # 첫 번째 VAEDecode 노드 ID
                    save_node["inputs"]["images"] = [vae_id, 0]
                    logger.info(f"SaveImage 노드 ID {save_id}에 VAEDecode 노드 ID {vae_id} 연결")
                
                # filename_prefix 확인
                if "filename_prefix" not in save_node["inputs"]:
                    save_node["inputs"]["filename_prefix"] = "ComfyUI"
        
        # 워크플로우를 ComfyUI API 형식으로 변환
        prompt_data = {}
        
        # 노드를 처리하여 API 형식에 맞게 변환
        for node in workflow["nodes"]:
            if "id" not in node or "class_type" not in node and "type" not in node:
                logger.warning(f"유효하지 않은 노드 스킵: {node}")
                continue
            
            node_id = str(node["id"])
            node_data = {}
            
            # ID를 제외한 모든 속성 복사
            for key, value in node.items():
                if key != "id":
                    node_data[key] = value
            
            # class_type 확인
            if "class_type" not in node_data and "type" in node:
                node_data["class_type"] = node["type"]
            
            prompt_data[node_id] = node_data
        
        # 최종 API 요청을 구성 - links 키 없이 노드만 사용
        api_request = {
            "prompt": prompt_data,
            "client_id": client_id
        }
        
        # JSON 변환
        try:
            data = json.dumps(api_request)
            logger.info(f"JSON 변환 성공: {len(data)} 바이트")
            data = data.encode('utf-8')
        except Exception as e:
            logger.error(f"JSON 변환 중 오류 발생: {str(e)}")
            logger.error(f"문제가 발생한 데이터 구조: {type(api_request)}")
            raise HTTPException(status_code=500, detail=f"JSON 변환 오류: {str(e)}")
        
        # API 요청 전송
        logger.info(f"API 요청 URL: http://{ip}/prompt")
        
        req = request.Request(f"http://{ip}/prompt", data=data)
        req.add_header('Content-Type', 'application/json')
        
        # 서버 요청 및 응답 처리
        try:
            res = request.urlopen(req)
            if res.status != 200:
                raise Exception(f"Error: {res.status} {res.reason}")
            
            # 응답 데이터 읽기
            response_text = res.read().decode('utf-8')
            
            # 예외 처리로 JSON 파싱 (예상치 못한 응답 형식에 대비)
            try:
                response_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"응답 JSON 파싱 오류: {str(e)}")
                # 정규식으로 prompt_id 추출 시도
                import re
                match = re.search(r'"prompt_id"\s*:\s*"([^"]+)"', response_text)
                if match:
                    prompt_id = match.group(1)
                    logger.info(f"정규식으로 prompt_id를 추출했습니다: {prompt_id}")
                    return prompt_id
                    
                match = re.search(r'"prompt_id"\s*:\s*(\d+)', response_text)
                if match:
                    prompt_id = match.group(1)
                    logger.info(f"정규식으로 숫자 prompt_id를 추출했습니다: {prompt_id}")
                    return prompt_id
                
                logger.error(f"응답에서 prompt_id를 찾을 수 없습니다. 응답: {response_text[:200]}")
                raise HTTPException(status_code=500, detail="응답 형식 오류: JSON이 아님")
                
            # 응답 형식 로깅
            logger.info(f"ComfyUI 서버 응답 형식: {type(response_data).__name__}")
            
            # prompt_id 추출
            prompt_id = None
            
            # 응답 타입별 처리
            if isinstance(response_data, dict):
                # 딕셔너리 응답인 경우 (일반적인 경우)
                if 'prompt_id' in response_data:
                    prompt_id = response_data['prompt_id']
                    logger.info(f"응답에서 prompt_id를 찾았습니다: {prompt_id}")
                else:
                    logger.warning(f"딕셔너리 응답에 prompt_id가 없습니다: {list(response_data.keys())}")
            elif isinstance(response_data, list):
                # 리스트 응답인 경우
                logger.warning(f"ComfyUI 서버가 리스트 형태로 응답했습니다. 리스트 길이: {len(response_data)}")
                
                if len(response_data) > 0:
                    # 첫 번째 항목이 딕셔너리인지 확인
                    if isinstance(response_data[0], dict) and 'prompt_id' in response_data[0]:
                        prompt_id = response_data[0]['prompt_id']
                        logger.info(f"리스트 응답의 첫 항목에서 prompt_id를 찾았습니다: {prompt_id}")
                    else:
                        # 각 항목에 prompt_id가 있는지 확인
                        for i, item in enumerate(response_data):
                            if isinstance(item, dict) and 'prompt_id' in item:
                                prompt_id = item['prompt_id']
                                logger.info(f"리스트 응답의 {i+1}번째 항목에서 prompt_id를 찾았습니다: {prompt_id}")
                                break
                        
                        if not prompt_id:
                            # 문자열로만 된 리스트인 경우
                            if len(response_data) == 1 and isinstance(response_data[0], str):
                                prompt_id = response_data[0].strip()
                                logger.info(f"리스트 응답의 첫 항목이 문자열입니다. 이를 prompt_id로 사용: {prompt_id}")
            elif isinstance(response_data, str):
                # 문자열 응답인 경우
                prompt_id = response_data.strip()
                logger.info(f"문자열 응답을 prompt_id로 사용: {prompt_id}")
            else:
                # 기타 타입 응답
                logger.error(f"예상치 못한 응답 형식: {type(response_data).__name__}")
                logger.error(f"응답 내용(일부): {str(response_data)[:300]}")
                
            if not prompt_id:
                # 응답 전체 내용에서 prompt_id를 검색
                if '"prompt_id":' in response_text:
                    logger.warning("응답 텍스트에서 prompt_id를 직접 검색합니다")
                    try:
                        # 정규식으로 prompt_id 추출 시도
                        import re
                        match = re.search(r'"prompt_id"\s*:\s*"([^"]+)"', response_text)
                        if match:
                            prompt_id = match.group(1)
                            logger.info(f"정규식으로 prompt_id를 추출했습니다: {prompt_id}")
                        else:
                            match = re.search(r'"prompt_id"\s*:\s*(\d+)', response_text)
                            if match:
                                prompt_id = match.group(1)
                                logger.info(f"정규식으로 숫자 prompt_id를 추출했습니다: {prompt_id}")
                    except Exception as e:
                        logger.error(f"정규식 prompt_id 추출 중 오류: {str(e)}")
            
            if not prompt_id:
                logger.error("응답에서 prompt_id를 찾을 수 없습니다")
                raise HTTPException(status_code=500, detail=f"ComfyUI 서버 응답 오류: prompt_id를 찾을 수 없음\n응답: {response_text[:200]}")
            
            return prompt_id
            
        except HTTPException as e:
            # HTTP 예외 그대로 전달
            raise e
        except Exception as e:
            error_msg = str(e)
            logger.error(f"ComfyUI 서버 요청 중 오류: {error_msg}")
            
            # 오류 내용 자세히 분석
            if hasattr(e, 'read') and callable(getattr(e, 'read')):
                try:
                    error_content = e.read().decode('utf-8')
                    logger.error(f"오류 상세 내용: {error_content}")
                except Exception as read_e:
                    logger.error(f"오류 내용 읽기 실패: {str(read_e)}")
            
            raise HTTPException(status_code=500, detail=f"ComfyUI 서버 연결 오류: {error_msg}")
    
    except HTTPException as e:
        # 이미 HTTPException으로 처리된 경우 그대로 전달
        raise e
    except Exception as e:
        error_msg = str(e)
        logger.error(f"ComfyUI 서버 연결 오류: {error_msg}")
        
        # 오류 내용 자세히 분석
        if hasattr(e, 'read') and callable(getattr(e, 'read')):
            try:
                error_content = e.read().decode('utf-8')
                logger.error(f"오류 상세 내용: {error_content}")
            except Exception as read_e:
                logger.error(f"오류 내용 읽기 실패: {str(read_e)}")
                
        raise HTTPException(status_code=500, detail=f"ComfyUI 서버 연결 오류: {error_msg}")

async def check_progress(prompt_id: str, ip: str):
    """이미지 생성 진행 상황 확인"""
    try:
        # 이미지 생성 시작 전 히스토리 상태 저장
        req = request.Request(f"http://{ip}/history")
        res = request.urlopen(req)
        if res.status != 200:
            raise Exception(f"히스토리 조회 실패: {res.status} {res.reason}")
            
        history_before = json.loads(res.read().decode('utf-8'))
        logger.info(f"현재 히스토리에 {len(history_before)} 개의 항목이 있습니다")
        
        # 최대 3분(180초) 대기
        max_attempts = 180
        for attempt in range(max_attempts):
            req = request.Request(f"http://{ip}/history")
            res = request.urlopen(req)
            if res.status != 200:
                logger.warning(f"히스토리 조회 실패: {res.status} {res.reason}")
                await asyncio.sleep(1)
                continue
                
            current_history = json.loads(res.read().decode('utf-8'))
            
            # 요청한 prompt_id의 결과 확인
            if prompt_id in current_history and "outputs" in current_history[prompt_id]:
                logger.info(f"생성 완료: prompt_id={prompt_id}")
                return current_history[prompt_id]
            
            # 모든 새로운 히스토리 항목 확인 (prompt_id가 변경됐을 가능성 대비)
            for hist_prompt_id, hist_data in current_history.items():
                if hist_prompt_id not in history_before and "outputs" in hist_data:
                    # SaveImage 노드 출력 확인 (노드 ID는 다를 수 있음)
                    for node_id, output in hist_data["outputs"].items():
                        if "images" in output and len(output["images"]) > 0:
                            logger.info(f"새 prompt_id={hist_prompt_id}에서 이미지 생성 완료")
                            return hist_data
            
            # 1초 대기 후 다시 확인
            await asyncio.sleep(1)
            
        # 시간 초과
        logger.error(f"이미지 생성 시간 초과: prompt_id={prompt_id}")
        raise HTTPException(status_code=408, detail="이미지 생성 시간 초과")
        
    except HTTPException as e:
        # 이미 HTTPException이면 그대로 전달
        raise e
    except Exception as e:
        logger.error(f"진행 상황 확인 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"진행 상황 확인 중 오류 발생: {str(e)}")

def create_basic_workflow(request: PromptRequest):
    """기본 워크플로우 생성 (Flux 워크플로우를 찾을 수 없을 때 사용)"""
    logger.info(f"기본 워크플로우 생성: 배치 크기={request.batch_size}")
    
    # 노드 ID 설정
    checkpoint_node_id = "1"
    positive_prompt_node_id = "2"
    empty_latent_node_id = "3"
    ksampler_node_id = "4"
    decoder_node_id = "5"
    save_image_node_id = "6"
    
    # 워크플로우 기본 구조
    workflow = {
        "nodes": [
            # 1. 체크포인트 로더
            {
                "id": checkpoint_node_id,
                "class_type": "CheckpointLoaderSimple",
                "widgets_values": ["v1-5-pruned-emaonly.safetensors"],
                "inputs": {}
            },
            # 2. 텍스트 인코더 (포지티브 프롬프트)
            {
                "id": positive_prompt_node_id,
                "class_type": "CLIPTextEncode",
                "widgets_values": [request.prompt],
                "inputs": {
                    "clip": [checkpoint_node_id, 0]
                }
            },
            # 3. 빈 레이턴트 이미지 생성
            {
                "id": empty_latent_node_id,
                "class_type": "EmptyLatentImage",
                "widgets_values": [1024, 1024, request.batch_size],
                "inputs": {}
            },
            # 4. KSampler (샘플링)
            {
                "id": ksampler_node_id,
                "class_type": "KSampler",
                "widgets_values": [
                    request.seed if request.seed is not None else 0,
                    request.steps,
                    7.0,  # CFG 스케일
                    "euler_ancestral",  # 샘플러
                    "normal",  # 샘플러 타입
                ],
                "inputs": {
                    "model": [checkpoint_node_id, 0],
                    "positive": [positive_prompt_node_id, 0],
                    "negative": [],
                    "latent_image": [empty_latent_node_id, 0]
                }
            },
            # 5. VAE 디코더
            {
                "id": decoder_node_id,
                "class_type": "VAEDecode",
                "widgets_values": [],
                "inputs": {
                    "samples": [ksampler_node_id, 0],
                    "vae": [checkpoint_node_id, 2]
                }
            },
            # 6. 이미지 저장
            {
                "id": save_image_node_id,
                "class_type": "SaveImage",
                "widgets_values": ["ComfyUI"],
                "inputs": {
                    "images": [decoder_node_id, 0],
                    "filename_prefix": "ComfyUI"  # 파일명 접두어 추가
                }
            }
        ],
        "links": [
            # 모델 -> 프롬프트 인코더 (clip)
            [checkpoint_node_id, 0, positive_prompt_node_id, 0],
            # 프롬프트 -> 샘플러
            [positive_prompt_node_id, 0, ksampler_node_id, 1],
            # 모델 -> 샘플러
            [checkpoint_node_id, 0, ksampler_node_id, 0],
            # 레이턴트 이미지 -> 샘플러
            [empty_latent_node_id, 0, ksampler_node_id, 3],
            # 샘플러 -> 디코더
            [ksampler_node_id, 0, decoder_node_id, 0],
            # VAE -> 디코더
            [checkpoint_node_id, 2, decoder_node_id, 1],
            # 디코더 -> 이미지 저장
            [decoder_node_id, 0, save_image_node_id, 0]
        ]
    }
    
    logger.info("기본 워크플로우 생성 완료")
    return workflow

@router.post("/generate")
async def generate_image(request: PromptRequest, current_user: User = Depends(get_current_user)):
    """텍스트 프롬프트로부터 이미지 생성"""
    logger.info(f"이미지 생성 요청: 프롬프트='{request.prompt[:30]}...', 배치 크기={request.batch_size}")
    
    try:
        # 1. 워크플로우 로드 - 실패 시 기본 워크플로우 사용
        logger.info("워크플로우 로드 중...")
        try:
            workflow = load_flux_workflow()
            logger.info("Flux 워크플로우 로드 완료")
        except FileNotFoundError as e:
            logger.warning(f"Flux 워크플로우 파일을 찾을 수 없습니다: {str(e)}")
            # 기본 워크플로우 생성
            workflow = create_basic_workflow(request)
            logger.info("기본 워크플로우로 대체합니다")
        except Exception as e:
            logger.error(f"워크플로우 로드 중 오류 발생: {str(e)}")
            raise HTTPException(status_code=500, detail=f"워크플로우 로드 실패: {str(e)}")
        
        # 2. 워크플로우 수정
        logger.info("워크플로우 수정 중...")
        modified_workflow = modify_workflow_with_prompt(workflow, request)
        logger.info("워크플로우 수정 완료")

        # 3. 클라이언트 ID 생성 (사용자 ID 포함)
        client_id = f"dp_management_{current_user.username}"
        
        # 4. ComfyUI에 전송
        logger.info("ComfyUI 서버에 요청 전송 중...")
        prompt_id = queue_prompt(modified_workflow, COMFYUI_IP, client_id)
        logger.info(f"ComfyUI 응답 받음: prompt_id={prompt_id}")
        
        # 5. 결과 대기 및 확인
        logger.info("이미지 생성 결과 대기 중...")
        result = await check_progress(prompt_id, COMFYUI_IP)
        logger.info("이미지 생성 완료, 결과 처리 중...")
        
        # 6. 생성된 모든 이미지 URL 추출
        all_images = []
        
        if "outputs" in result:
            # 모든 노드의 출력 확인
            for node_id, node_output in result["outputs"].items():
                if "images" in node_output:
                    for image in node_output["images"]:
                        # 이미지 URL 생성
                        image_url = f"http://{COMFYUI_IP}/view?filename={image['filename']}&type={image.get('type', 'output')}"
                        logger.info(f"이미지 생성 성공: {image['filename']}")
                        
                        # 이미지 정보 추가
                        all_images.append({
                            "url": image_url,
                            "filename": image["filename"]
                        })
        
        if all_images:
            # 모든 이미지 정보 반환
            logger.info(f"총 {len(all_images)}개 이미지 생성 완료")
            return {
                "success": True,
                "batch_size": request.batch_size,
                "images": all_images
            }
        
        # 이미지가 생성되지 않음
        logger.warning("이미지 출력을 찾을 수 없음")
        return {"success": False, "error": "이미지가 생성되지 않았습니다."}
        
    except HTTPException as e:
        logger.error(f"HTTP 예외 발생: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"이미지 생성 중 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"이미지 생성 중 오류 발생: {str(e)}") 