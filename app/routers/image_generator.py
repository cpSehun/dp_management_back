from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, FileResponse
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
import json
import os
import requests
import logging
from pathlib import Path
import uuid
import time
from app.database import get_db
from pydantic import BaseModel

# 로깅 설정
logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter()

# 작업 디렉토리 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORKFLOW_FILE = BASE_DIR / 'flux1-dev.json'
API_FILE = BASE_DIR / 'flux1-dev-api.json'
# Docker 환경에서는 /app/output 경로 사용
OUTPUT_DIR = Path('/app/output')

# 현재 경로 로깅
logger.info(f"현재 실행 경로: {Path.cwd()}")
logger.info(f"BASE_DIR: {BASE_DIR}")
logger.info(f"OUTPUT_DIR: {OUTPUT_DIR}")

# 출력 디렉토리가 없으면 생성
if not OUTPUT_DIR.exists():
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"출력 디렉토리 생성 완료: {OUTPUT_DIR}")
    except Exception as e:
        logger.error(f"출력 디렉토리 생성 실패: {e}")

# 출력 디렉토리 접근 권한 확인
try:
    test_file_path = OUTPUT_DIR / 'test_write.txt'
    with open(test_file_path, 'w') as f:
        f.write('test')
    test_file_path.unlink()  # 테스트 파일 삭제
    logger.info(f"출력 디렉토리 쓰기 권한 확인 완료: {OUTPUT_DIR}")
except Exception as e:
    logger.error(f"출력 디렉토리 쓰기 권한 없음: {e}")

# Pydantic 모델 정의
class ImageRequest(BaseModel):
    prompt: str
    steps: int
    batch_size: int
    negative_prompt: Optional[str] = None
    width: Optional[int] = 1024
    height: Optional[int] = 1024
    guidance: Optional[float] = 3.5
    seed: Optional[int] = None

class ImageResponse(BaseModel):
    job_id: str
    status: str
    message: str

# ComfyUI API 설정
COMFYUI_SERVER = os.getenv("COMFYUI_SERVER", "http://192.168.0.151:8188")

# ComfyUI API 요청을 위한 엔드포인트 생성 함수
def get_comfyui_endpoint(path):
    # URL이 http:// 또는 https://로 시작하는지 확인
    if COMFYUI_SERVER.startswith(('http://', 'https://')):
        base_url = COMFYUI_SERVER
    else:
        base_url = f"http://{COMFYUI_SERVER}"
    
    # 경로가 /로 시작하는지 확인
    if path.startswith('/'):
        return f"{base_url}{path}"
    else:
        return f"{base_url}/{path}"

# 워크플로우 로드 함수
def load_workflow():
    try:
        with open(API_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"워크플로우 파일을 로드하는 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="워크플로우 파일을 로드할 수 없습니다")

# 워크플로우 수정 함수 (사용자 입력 적용)
def modify_workflow(workflow_data: Dict, request: ImageRequest):
    try:
        # 워크플로우 복사본 생성
        modified_workflow = workflow_data.copy()
        
        # 텍스트 프롬프트 수정 (positive prompt)
        if "6" in modified_workflow:  # CLIP Text Encode (Positive Prompt) 노드
            modified_workflow["6"]["inputs"]["text"] = request.prompt
        
        # 이미지 크기 및 배치 크기 설정
        if "27" in modified_workflow:  # Empty Latent Image 노드
            modified_workflow["27"]["inputs"]["width"] = request.width
            modified_workflow["27"]["inputs"]["height"] = request.height
            modified_workflow["27"]["inputs"]["batch_size"] = request.batch_size
        
        # 가이던스 스케일 설정
        if "26" in modified_workflow:  # FluxGuidance 노드
            modified_workflow["26"]["inputs"]["guidance"] = request.guidance
        
        # 스텝 수 설정
        if "17" in modified_workflow:  # BasicScheduler 노드
            modified_workflow["17"]["inputs"]["steps"] = request.steps
        
        # 시드 설정
        if "25" in modified_workflow and request.seed is not None:  # RandomNoise 노드
            modified_workflow["25"]["inputs"]["noise_seed"] = request.seed
        
        return modified_workflow
    except Exception as e:
        logger.error(f"워크플로우 수정 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"워크플로우 수정 중 오류: {str(e)}")

# ComfyUI로 워크플로우 전송 함수
async def send_workflow_to_comfyui(workflow_data: Dict):
    try:
        url = get_comfyui_endpoint("api/prompt")
        logger.info(f"ComfyUI API 요청 URL: {url}")
        response = requests.post(url, json={"prompt": workflow_data})
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"ComfyUI API 오류: {response.status_code} - {response.text}")
            raise HTTPException(status_code=response.status_code, detail=f"ComfyUI API 오류: {response.text}")
    except requests.RequestException as e:
        logger.error(f"ComfyUI API 요청 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"ComfyUI API 요청 중 오류: {str(e)}")

# 작업 완료 대기 함수
async def wait_for_job_completion(job_id: str, max_retries=120):
    """이미지 생성 작업이 완료될 때까지 대기"""
    for i in range(max_retries):
        try:
            url = get_comfyui_endpoint(f"api/history/{job_id}")
            response = requests.get(url)
            
            if response.status_code == 200:
                result = response.json()
                
                # 작업 객체 가져오기 (응답이 {job_id: {...}} 형태)
                job_result = result.get(job_id, {})
                
                # 작업 완료 확인 - status.completed 필드 확인
                if job_result.get('status', {}).get('completed', False):
                    logger.info(f"작업 완료 확인: {job_id}")
                    return job_result
                
                # 또는 outputs 필드가 있고 비어있지 않은지도 확인
                if "outputs" in job_result and job_result["outputs"]:
                    logger.info(f"작업 완료 확인(outputs): {job_id}")
                    return job_result
                
                # 작업 실패 확인
                if job_result.get('status', {}).get('status_str') == 'error':
                    logger.warning(f"작업 실패: {job_id} - {job_result.get('status', {}).get('error')}")
                    return job_result
            
            # 아직 완료되지 않았으면 1초 대기
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"작업 상태 확인 중 오류: {e}")
            time.sleep(1)
    
    # 모든 시도에서 작업 완료를 확인하지 못한 경우, 한 번 더 확인
    try:
        logger.warning(f"마지막 확인 시도: {job_id}")
        url = get_comfyui_endpoint(f"api/history/{job_id}")
        response = requests.get(url)
        
        if response.status_code == 200:
            result = response.json()
            logger.debug(f"마지막 확인 결과: {result}")
            
            # 작업 객체 가져오기
            if job_id in result:
                job_result = result.get(job_id, {})
                
                # 작업이 완료되었거나 실패했는지 최종 확인
                if job_result.get('status', {}).get('completed', False) or "outputs" in job_result:
                    return job_result
                elif job_result.get('status', {}).get('status_str') == 'error':
                    logger.warning(f"작업 실패 확인: {job_id} - {job_result.get('status', {}).get('error')}")
                    return job_result
                else:
                    logger.warning(f"작업 상태 불확실: {job_id}")
    except Exception as e:
        logger.error(f"마지막 확인 중 오류: {e}")
    
    logger.warning(f"최대 대기 시간 초과(2분): {job_id}")
    return None

# 이미지 다운로드 및 저장 함수
async def download_comfyui_images(job_id: str, results: Dict):
    """ComfyUI에서 생성된 이미지를 다운로드하여 저장"""
    saved_images = []
    
    try:
        if not results:
            logger.error(f"결과가 없습니다")
            return saved_images
        
        # 워크플로우 정보에서 노드 이름 정보 추출 (있는 경우)
        node_types = {}
        if "prompt" in results and isinstance(results["prompt"], list) and len(results["prompt"]) > 2:
            workflow = results["prompt"][2]
            for node_id, node_info in workflow.items():
                if isinstance(node_info, dict) and "class_type" in node_info:
                    node_types[node_id] = node_info.get("class_type", "Unknown")
                    # _meta 정보에서 title이 있으면 그것을 사용
                    if "_meta" in node_info and "title" in node_info["_meta"]:
                        node_types[node_id] = node_info["_meta"]["title"]
            
            # DEBUG 레벨로 변경하여 일반 로그에는 표시되지 않도록 함
            logger.debug(f"워크플로우에서 추출한 노드 타입 정보: {node_types}")
        
        # ComfyUI API에서는 outputs 필드 확인
        if "outputs" in results:
            outputs = results["outputs"]
            # DEBUG 레벨로 변경
            logger.debug(f"outputs 필드 사용: {outputs}")
        else:
            logger.info(f"outputs 필드 없음, API 재호출")
            # API 재호출하여 최신 정보 가져오기
            url = get_comfyui_endpoint(f"api/history/{job_id}")
            response = requests.get(url)
            if response.status_code == 200:
                new_results = response.json()
                job_result = new_results.get(job_id, {})
                
                # 워크플로우 정보 추출 시도
                if "prompt" in job_result and isinstance(job_result["prompt"], list) and len(job_result["prompt"]) > 2:
                    workflow = job_result["prompt"][2]
                    for node_id, node_info in workflow.items():
                        if isinstance(node_info, dict) and "class_type" in node_info:
                            node_types[node_id] = node_info.get("class_type", "Unknown")
                            # _meta 정보에서 title이 있으면 그것을 사용
                            if "_meta" in node_info and "title" in node_info["_meta"]:
                                node_types[node_id] = node_info["_meta"]["title"]
                    
                    # DEBUG 레벨로 변경
                    logger.debug(f"API 재호출로 추출한 노드 타입 정보: {node_types}")
                
                if "outputs" in job_result:
                    outputs = job_result["outputs"]
                    # DEBUG 레벨로 변경
                    logger.debug(f"API 재호출 결과 outputs: {outputs}")
                else:
                    # outputs 필드가 없으면 빈 목록 반환
                    logger.error("outputs 필드를 찾을 수 없어 이미지를 가져올 수 없습니다")
                    return saved_images
            else:
                logger.error(f"API 재호출 실패: {response.status_code}")
                return saved_images
        
        # 각 출력 노드에서 이미지 찾기
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                images = node_output["images"]
                # DEBUG 레벨로 변경
                logger.debug(f"노드 {node_id}의 이미지: {images}")
                
                # 노드 타입 정보 가져오기 (이제 불필요하지만 로깅을 위해 유지)
                node_type = node_types.get(node_id, "SaveImage")
                
                # 각 이미지 다운로드 및 저장
                for i, img_data in enumerate(images):
                    # ComfyUI에서 반환된 파일명, subfolder, type 정보 사용
                    comfy_filename = img_data.get("filename", "")
                    comfy_subfolder = img_data.get("subfolder", "")
                    comfy_type = img_data.get("type", "output")
                    
                    if not comfy_filename:
                        logger.warning(f"이미지 데이터에 filename이 없습니다: {img_data}")
                        continue
                    
                    # 로컬에 저장할 파일명 설정
                    filename = f"{job_id}_{i}.png"
                    filepath = OUTPUT_DIR / filename
                    
                    # 경로 확인 로깅 - DEBUG 레벨로 변경
                    logger.debug(f"저장 파일 경로: {filepath} (존재: {filepath.parent.exists()})")
                    
                    # ComfyUI에서 이미지 URL 생성 (정확한 파일명과 타입 사용)
                    img_url = get_comfyui_endpoint(f"view?filename={comfy_filename}&subfolder={comfy_subfolder}&type={comfy_type}")
                    logger.debug(f"이미지 다운로드 URL: {img_url}")
                    
                    try:
                        # 이미지 다운로드 및 저장
                        response = requests.get(img_url, stream=True)
                        if response.status_code == 200:
                            # 파일 크기 확인 - DEBUG 레벨로 변경
                            content_length = int(response.headers.get('content-length', 0))
                            logger.debug(f"이미지 크기: {content_length} 바이트")
                            
                            # 디렉토리 확인
                            if not filepath.parent.exists():
                                filepath.parent.mkdir(parents=True, exist_ok=True)
                                logger.info(f"부모 디렉토리 생성: {filepath.parent}")
                            
                            # 파일 저장
                            with open(filepath, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            
                            # 파일 확인
                            if filepath.exists():
                                filesize = filepath.stat().st_size
                                logger.info(f"이미지 저장 완료: {i+1}/{len(images)} - {filepath.name}")
                                
                                saved_images.append({
                                    "url": f"/api/v1/image-generator/outputs/{filename}",
                                    "filename": f"generated_image_{filename}",
                                    "original_url": img_url  # 원본 ComfyUI URL도 추가
                                })
                            else:
                                logger.error(f"파일이 저장되지 않음: {filepath}")
                        else:
                            logger.error(f"이미지 다운로드 실패: {response.status_code} - URL: {img_url}")
                    except Exception as e:
                        logger.error(f"이미지 저장 중 오류: {e}, 파일 경로: {filepath}")
    
    except Exception as e:
        logger.error(f"이미지 다운로드 중 오류: {e}")
    
    return saved_images

# 이미지 생성 API 엔드포인트
@router.post("/generate", response_model=Dict[str, Any])
async def generate_image(
    request: ImageRequest,
    db: Session = Depends(get_db)
):
    try:
        # 워크플로우 로드 및 수정
        workflow_data = load_workflow()
        modified_workflow = modify_workflow(workflow_data, request)
        
        # ComfyUI로 워크플로우 전송
        response = await send_workflow_to_comfyui(modified_workflow)
        
        if not response:
            return {
                "success": False,
                "error": "이미지 생성 요청이 실패했습니다"
            }
        
        # job_id 가져오기
        job_id = str(uuid.uuid4())
        if "prompt_id" in response:
            job_id = response["prompt_id"]
            logger.info(f"작업 ID: {job_id}")
        
        # 이미지 생성 완료 대기
        results = await wait_for_job_completion(job_id)
        
        if not results:
            return {
                "success": False,
                "error": "이미지 생성 시간이 초과되었습니다"
            }
        
        # 이미지 다운로드 및 저장
        images = await download_comfyui_images(job_id, results)
        
        if not images:
            return {
                "success": False,
                "error": "이미지를 다운로드할 수 없습니다"
            }
        
        # 디버깅을 위해 이미지 JSON 정보 로깅 - DEBUG 레벨로 변경
        logger.debug(f"반환되는 이미지 정보: {json.dumps(images, ensure_ascii=False)}")
        
        # 성공 응답 반환
        logger.info(f"이미지 생성 완료: {len(images)}개")
        return {
            "success": True,
            "job_id": job_id,
            "images": images,
            "message": "이미지 생성이 완료되었습니다"
        }
        
    except Exception as e:
        logger.error(f"이미지 생성 오류: {e}")
        return {
            "success": False,
            "error": f"이미지 생성 중 오류가 발생했습니다: {str(e)}"
        }

# 저장된 이미지 제공 엔드포인트
@router.get("/outputs/{filename}", response_class=FileResponse)
async def get_generated_image(filename: str):
    file_path = OUTPUT_DIR / filename
    
    # DEBUG 레벨로 변경
    logger.debug(f"이미지 요청: {filename}, 경로: {file_path}, 존재: {file_path.exists()}")
    
    if not file_path.exists():
        logger.error(f"이미지 파일이 존재하지 않습니다: {file_path}")
        raise HTTPException(status_code=404, detail=f"이미지를 찾을 수 없습니다: {filename}")
    
    try:
        return FileResponse(file_path)
    except Exception as e:
        logger.error(f"이미지 제공 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"이미지 제공 중 오류: {str(e)}")

# 이미지 생성 상태 확인 API 엔드포인트
@router.get("/status/{job_id}", response_model=Dict[str, Any])
async def check_image_status(job_id: str):
    try:
        # ComfyUI API에서 작업 상태 확인
        url = get_comfyui_endpoint(f"api/history/{job_id}")
        response = requests.get(url)
        
        if response.status_code == 200:
            result = response.json()
            # API 응답에서 작업 객체 가져오기 (응답이 {job_id: {...}} 형태)
            job_result = result.get(job_id, {})
            
            if not job_result:
                return {
                    "job_id": job_id,
                    "status": "not_found",
                    "message": "작업을 찾을 수 없습니다"
                }
            
            return {
                "job_id": job_id,
                "status": "completed" if "outputs" in job_result and job_result["outputs"] else "processing",
                "result": job_result
            }
        else:
            return {
                "job_id": job_id,
                "status": "error",
                "message": f"작업 상태를 가져올 수 없습니다: {response.text}"
            }
    except Exception as e:
        logger.error(f"작업 상태 확인 중 오류 발생: {e}")
        return {
            "job_id": job_id,
            "status": "error",
            "message": f"작업 상태 확인 중 오류: {str(e)}"
        }

# 이미지 목록 가져오기 API 엔드포인트
@router.get("/images", response_model=List[Dict[str, Any]])
async def list_images():
    try:
        # ComfyUI API에서 이미지 히스토리 가져오기
        url = get_comfyui_endpoint("api/history")
        response = requests.get(url)
        
        if response.status_code == 200:
            history = response.json()
            result = []
            
            # 각 작업에 대한 정보 추출
            for job_id, data in history.items():
                # 작업 완료 상태 확인
                is_completed = False
                if "status" in data and data["status"].get("completed", False):
                    is_completed = True
                elif "outputs" in data and data["outputs"]:
                    is_completed = True
                
                result.append({
                    "job_id": job_id,
                    "timestamp": data.get("timestamp", 0),
                    "status": "completed" if is_completed else "processing"
                })
            
            return result
        else:
            raise HTTPException(status_code=response.status_code, detail=f"이미지 목록을 가져올 수 없습니다: {response.text}")
    except Exception as e:
        logger.error(f"이미지 목록 가져오기 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"이미지 목록 가져오기 중 오류: {str(e)}")
