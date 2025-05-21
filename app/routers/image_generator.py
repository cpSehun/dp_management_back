from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
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
from pydantic import BaseModel, Field
import base64 # base64 디코딩을 위해 추가

# S3 유틸리티 임포트
from app.utils.s3 import upload_file_to_s3, get_s3_client # get_s3_client는 직접 사용하지 않더라도 s3 모듈 초기화 등을 위해 임포트할 수 있음

# 이미지 생성기 모듈 임포트
from app.image_generators.factory import ImageGeneratorFactory


# 로깅 설정
logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter()

# 작업 디렉토리 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORKFLOW_FILE = BASE_DIR / 'flux1-dev.json'
API_FILE = BASE_DIR / 'flux1-dev-api.json'

# 현재 경로 로깅
logger.info(f"현재 실행 경로: {Path.cwd()}")
logger.info(f"BASE_DIR: {BASE_DIR}")


# Pydantic 모델 정의
class ImageRequest(BaseModel):
    prompt: str
    steps: int = 40
    batch_size: int = 1
    negative_prompt: Optional[str] = None
    width: Optional[int] = 1024
    height: Optional[int] = 1024
    guidance: Optional[float] = 3.5
    seed: Optional[int] = None
    model: Optional[str] = "flux-dev"  # 기본값은 flux-dev
    save_to_backend: Optional[bool] = True  # 백엔드에 이미지 저장 여부

class ImageResponse(BaseModel):
    job_id: str
    status: str
    message: str

# S3 저장 요청 모델
class S3SaveRequest(BaseModel):
    image_urls: List[str] = Field(..., description="S3에 저장할 ComfyUI 원본 이미지 URL 목록")
    # 필요하다면 프롬프트, 모델명 등의 추가 메타데이터도 포함 가능
    # prompt: Optional[str] = None
    # model_name: Optional[str] = None

# S3 저장 응답 모델
class S3SaveResponse(BaseModel):
    success: bool
    message: str
    saved_s3_urls: Optional[List[str]] = None
    failed_urls: Optional[List[str]] = None

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
    """ComfyUI에서 생성된 이미지 정보를 반환 (로컬 저장 안 함)"""
    returned_images = []
    
    try:
        if not results:
            logger.error(f"결과가 없습니다")
            return returned_images
        
        node_types = {}
        if "prompt" in results and isinstance(results["prompt"], list) and len(results["prompt"]) > 2:
            workflow = results["prompt"][2]
            for node_id, node_info in workflow.items():
                if isinstance(node_info, dict) and "class_type" in node_info:
                    node_types[node_id] = node_info.get("class_type", "Unknown")
                    if "_meta" in node_info and "title" in node_info["_meta"]:
                        node_types[node_id] = node_info["_meta"]["title"]
            logger.debug(f"워크플로우에서 추출한 노드 타입 정보: {node_types}")
        
        outputs = {}
        if "outputs" in results:
            outputs = results["outputs"]
            logger.debug(f"outputs 필드 사용: {outputs}")
        else:
            logger.info(f"outputs 필드 없음, API 재호출")
            url = get_comfyui_endpoint(f"api/history/{job_id}")
            response = requests.get(url)
            if response.status_code == 200:
                new_results = response.json()
                job_result = new_results.get(job_id, {})
                
                if "prompt" in job_result and isinstance(job_result["prompt"], list) and len(job_result["prompt"]) > 2:
                    workflow = job_result["prompt"][2]
                    for node_id, node_info in workflow.items():
                        if isinstance(node_info, dict) and "class_type" in node_info:
                            node_types[node_id] = node_info.get("class_type", "Unknown")
                            if "_meta" in node_info and "title" in node_info["_meta"]:
                                node_types[node_id] = node_info["_meta"]["title"]
                    logger.debug(f"API 재호출로 추출한 노드 타입 정보: {node_types}")
                
                if "outputs" in job_result:
                    outputs = job_result["outputs"]
                    logger.debug(f"API 재호출 결과 outputs: {outputs}")
                else:
                    logger.error("outputs 필드를 찾을 수 없어 이미지를 가져올 수 없습니다")
                    return returned_images
            else:
                logger.error(f"API 재호출 실패: {response.status_code}")
                return returned_images
        
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                images_data = node_output["images"]
                logger.debug(f"노드 {node_id}의 이미지 데이터: {images_data}")
                
                for i, img_data in enumerate(images_data):
                    comfy_filename = img_data.get("filename", "")
                    comfy_subfolder = img_data.get("subfolder", "")
                    comfy_type = img_data.get("type", "output")
                    
                    if not comfy_filename:
                        logger.warning(f"이미지 데이터에 filename이 없습니다: {img_data}")
                        continue
                    
                    img_url = get_comfyui_endpoint(f"view?filename={comfy_filename}&subfolder={comfy_subfolder}&type={comfy_type}")
                    logger.debug(f"ComfyUI 이미지 URL: {img_url}")
                    
                    returned_images.append({
                        "original_url": img_url,
                        "filename": comfy_filename,
                        "subfolder": comfy_subfolder,
                        "type": comfy_type,
                        "node_id": node_id,
                        "node_type": node_types.get(node_id, "Unknown")
                    })
                    logger.info(f"이미지 정보 추가: {i+1}/{len(images_data)} - {comfy_filename}")

    except Exception as e:
        logger.error(f"ComfyUI 이미지 정보 처리 중 오류: {e}")
    
    return returned_images

# 모델 목록 엔드포인트
@router.get("/models", response_model=List[Dict[str, str]])
async def list_models():
    """사용 가능한 이미지 생성 모델 목록 반환"""
    try:
        return ImageGeneratorFactory.list_generators()
    except Exception as e:
        logger.error(f"모델 목록 가져오기 오류: {e}")
        raise HTTPException(status_code=500, detail=f"모델 목록을 가져올 수 없습니다: {str(e)}")

# 이미지 생성 API 엔드포인트
@router.post("/generate", response_model=Dict[str, Any])
async def generate_image(
    request: ImageRequest,
    db: Session = Depends(get_db)
):
    try:
        # 요청된 모델에 맞는 생성기 가져오기
        model_name = request.model
        generator = ImageGeneratorFactory.get_generator(model_name)
        
        if not generator:
            return {
                "success": False,
                "error": f"지원하지 않는 모델입니다: {model_name}"
            }
        
        # 요청 데이터 준비
        request_data = request.dict()
        
        # 이미지 생성 요청
        result = await generator.generate(request_data)
        
        return result
        
    except Exception as e:
        logger.error(f"이미지 생성 오류: {e}")
        return {
            "success": False,
            "error": f"이미지 생성 중 오류가 발생했습니다: {str(e)}"
        }

# 이미지 생성 상태 확인 API 엔드포인트
@router.get("/status/{job_id}", response_model=Dict[str, Any])
async def check_image_status(
    job_id: str,
    model: Optional[str] = Query(None, description="이미지 생성에 사용된 모델명")
):
    try:
        # 모델이 지정되지 않은 경우 모든 모델에서 확인
        if not model:
            # 사용 가능한 모든 생성기에서 작업 확인
            for generator_info in ImageGeneratorFactory.list_generators():
                generator_name = generator_info["name"]
                generator = ImageGeneratorFactory.get_generator(generator_name)
                
                if not generator:
                    continue
                
                result = await generator.get_status(job_id)
                
                # 작업을 찾았으면 해당 결과 반환
                if result.get("status") != "not_found":
                    return result
            
            # 모든 생성기에서 작업을 찾지 못한 경우
            return {
                "job_id": job_id,
                "status": "not_found",
                "message": "작업을 찾을 수 없습니다"
            }
        
        # 모델이 지정된 경우 해당 모델에서만 확인
        generator = ImageGeneratorFactory.get_generator(model)
        
        if not generator:
            return {
                "job_id": job_id,
                "status": "error",
                "message": f"지원하지 않는 모델입니다: {model}"
            }
        
        return await generator.get_status(job_id)
        
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

# --- S3 저장 관련 기능 추가 ---

async def upload_image_to_s3_from_url(image_url: str) -> Optional[str]:
    """
    주어진 URL에서 이미지를 다운로드하거나 Base64 데이터를 디코딩하여 S3에 업로드하고 CloudFront URL을 반환합니다.
    """
    try:
        temp_dir = Path("/tmp/image_downloads") # Docker 환경 등을 고려하여 적절한 임시 경로 사용
        temp_dir.mkdir(parents=True, exist_ok=True)
        # 고유한 파일명 생성 (S3 오브젝트 키로 사용)
        # 파일 확장자는 URL에서 가져오거나, base64인 경우 기본 .png 사용
        extension = '.png' # 기본값
        s3_object_name = f"generated_image_{uuid.uuid4()}{extension}"
        temp_file_path = temp_dir / s3_object_name

        if image_url.startswith("data:image"): # Base64 Data URL 처리
            logger.info(f"Base64 Data URL 감지: {image_url[:100]}...")
            # "data:image/png;base64,xxxxxx" 형태에서 base64 부분만 추출
            try:
                header, encoded_data = image_url.split(",", 1)
                # header에서 mime type 추출 (예: image/jpeg, image/png)
                mime_type = header.split(";")[0].split(":")[1]
                if mime_type == "image/jpeg" or mime_type == "image/jpg":
                    extension = ".jpg"
                elif mime_type == "image/png":
                    extension = ".png"
                # 다른 이미지 타입에 대한 처리 추가 가능
                
                # s3_object_name과 temp_file_path를 확장자에 맞게 다시 설정
                s3_object_name = f"generated_image_{uuid.uuid4()}{extension}"
                temp_file_path = temp_dir / s3_object_name
                
                image_data = base64.b64decode(encoded_data)
                with open(temp_file_path, 'wb') as f:
                    f.write(image_data)
                logger.info(f"Base64 이미지 임시 저장 완료: {temp_file_path}")
            except Exception as e:
                logger.error(f"Base64 Data URL 처리 중 오류: {e}")
                return None
        else: # 일반 HTTP/HTTPS URL 처리
            logger.info(f"HTTP(S) URL 감지, 이미지 다운로드 시도: {image_url}")
            response = requests.get(image_url, stream=True)
            response.raise_for_status()  # HTTP 오류 발생 시 예외 발생

            # 파일 확장자 추론 (기본은 .png)
            content_type = response.headers.get('Content-Type', '')
            if 'jpeg' in content_type or 'jpg' in content_type:
                extension = '.jpg'
            elif 'png' in content_type:
                extension = '.png'
            
            # s3_object_name과 temp_file_path를 실제 콘텐츠 타입에 맞게 다시 설정
            s3_object_name = f"generated_image_{uuid.uuid4()}{extension}"
            temp_file_path = temp_dir / s3_object_name

            with open(temp_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"HTTP(S) 이미지 임시 저장 완료: {temp_file_path}")

        # S3에 업로드
        s3_url = upload_file_to_s3(file_path=temp_file_path, object_name=s3_object_name)
        
        # 임시 파일 삭제
        if temp_file_path.exists():
            temp_file_path.unlink()
            logger.info(f"임시 파일 삭제 완료: {temp_file_path}")

        if s3_url:
            logger.info(f"S3 업로드 성공: {s3_url}")
            return s3_url
        else:
            logger.error(f"S3 업로드 실패 (s3_url 없음): {image_url[:100]}...")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"이미지 다운로드 실패 (HTTP 요청 오류): {image_url[:100]}..., 오류: {e}")
        return None
    except Exception as e:
        logger.error(f"S3 업로드 중 예기치 않은 오류 발생: {image_url[:100]}..., 오류: {e}")
        # 실패 시 임시 파일이 남아있을 수 있으므로 정리 시도
        if 'temp_file_path' in locals() and temp_file_path.exists():
            try:
                temp_file_path.unlink()
                logger.info(f"오류 발생 후 임시 파일 삭제 시도: {temp_file_path}")
            except Exception as unlink_e:
                logger.error(f"오류 발생 후 임시 파일 삭제 실패: {unlink_e}")
        return None

@router.post("/s3/save-images", response_model=S3SaveResponse)
async def save_images_to_s3(
    request: S3SaveRequest,
    db: Session = Depends(get_db) # db 세션은 현재 사용되지 않지만, 추후 필요할 수 있어 유지
):
    """
    제공된 ComfyUI 이미지 URL 목록에서 이미지를 다운로드하여 S3에 저장합니다.
    """
    if not request.image_urls:
        return S3SaveResponse(
            success=False,
            message="저장할 이미지 URL이 제공되지 않았습니다."
        )

    # S3 클라이언트 및 설정 확인 (선택적이지만, 조기 실패에 도움될 수 있음)
    s3_client = get_s3_client()
    if not s3_client:
         return S3SaveResponse(success=False, message="S3 클라이언트를 초기화할 수 없습니다. AWS 설정을 확인하세요.")
    if not os.getenv("S3_BUCKET_NAME") or not os.getenv("CLOUDFRONT_DOMAIN_NAME"):
         return S3SaveResponse(success=False, message="S3 버킷 이름 또는 CloudFront 도메인 이름이 설정되지 않았습니다.")

    saved_s3_urls = []
    failed_urls = []

    for image_url in request.image_urls:
        s3_path = await upload_image_to_s3_from_url(image_url)
        if s3_path:
            saved_s3_urls.append(s3_path)
        else:
            failed_urls.append(image_url)
    
    if saved_s3_urls:
        message = f"{len(saved_s3_urls)}개의 이미지가 S3에 성공적으로 저장되었습니다."
        if failed_urls:
            message += f" {len(failed_urls)}개의 이미지 저장에 실패했습니다."
        return S3SaveResponse(
            success=True,
            message=message,
            saved_s3_urls=saved_s3_urls,
            failed_urls=failed_urls if failed_urls else None
        )
    else:
        return S3SaveResponse(
            success=False,
            message="모든 이미지 저장에 실패했습니다.",
            failed_urls=failed_urls
        )

# 이미지 저장 API 엔드포인트 추가 - 삭제
# @router.post("/save", response_model=Dict[str, Any])
# async def save_images(
# ... 기존 save_images 함수 내용 ...
# 이 함수는 이전 단계에서 삭제되었어야 합니다.
