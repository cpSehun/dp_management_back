"""
OpenAI GPT-4 Vision (gpt-image-1) 이미지 생성기

OpenAI의 이미지 생성 모델을 사용하여 이미지를 생성하는 구현체
"""
from typing import Dict, Any, List, Optional
import os
import json
import time
import requests # OpenAI API 직접 호출 시 필요
import logging
import base64
import uuid
from pathlib import Path # output_dir 관련 사용 안 함

from .base import ImageGenerator

# 로깅 설정
logger = logging.getLogger(__name__)

class GptImageGenerator(ImageGenerator):
    """GPT-4 Vision (gpt-image-1) 이미지 생성기"""
    name = "gpt-image-1"
    description = "OpenAI GPT-4 Vision을 사용한 이미지 생성"
    
    def __init__(self):
        """OpenAI 이미지 생성기 초기화"""
        super().__init__()
        
        # API 키 설정
        self.api_key = os.getenv("OPENAI_API_KEY") # 환경 변수명은 기존 것을 따름
        if not self.api_key:
            logger.warning("OPENAI_API_KEY가 설정되지 않았습니다. 환경 변수를 확인하세요.")
        
        # API 엔드포인트 설정 (DALL-E 2/3와 다를 수 있으므로, 기존 gpt-image-1에 맞게 설정)
        # self.api_url = "https://api.openai.com/v1/images/generations" # DALL-E 일반 엔드포인트
        # 만약 gpt-image-1 전용 엔드포인트나 다른 설정이 있다면 그에 맞게 수정 필요
        # 현재는 일반적인 이미지 생성 엔드포인트를 사용한다고 가정합니다.
        # DALL-E API는 모델명을 지정하여 호출하므로, 엔드포인트는 동일할 수 있습니다.
        self.api_url = "https://api.openai.com/v1/images/generations"
        
        # 진행 중인 작업 추적 (상태 관리가 필요하다면 유지)
        self.jobs: Dict[str, Dict[str, Any]] = {}
        
        # self.output_dir 관련 설정 제거
        logger.info(f"GptImageGenerator (gpt-image-1) 초기화 완료. API URL: {self.api_url}")

    async def generate(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        이미지 생성 메서드
        save_to_backend 파라미터는 무시하고, 항상 URL 또는 base64 데이터를 반환합니다.
        """
        try:
            # save_to_backend 파라미터는 더 이상 사용하지 않음
            # save_to_backend = request_data.get("save_to_backend", True)
            
            if not self.api_key:
                return {
                    "success": False,
                    "error": "OpenAI API 키가 설정되지 않았습니다. 환경 변수를 확인하세요."
                }
            
            job_id = self.generate_job_id() 
            logger.info(f"OpenAI(gpt-image-1) 이미지 생성 요청 시작. Job ID: {job_id}")

            # OpenAI API 요청 데이터 준비 (gpt-image-1 모델에 맞게)
            payload = {
                "model": "gpt-image-1", 
                "prompt": request_data.get("prompt", ""),
                "n": request_data.get("batch_size", 1),
                "size": f"{request_data.get('width', 1024)}x{request_data.get('height', 1024)}"
    
            }
            
            # 작업 상태 설정 (선택적)
            self.jobs[job_id] = {
                "status": "processing",
                "request_payload": payload, # 요청 페이로드 저장 (디버깅용)
                "start_time": time.time()
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # 비동기 요청을 위해 httpx 또는 aiohttp 사용 고려 가능하나, 우선 동기 requests 사용
            # async로 선언된 함수 내에서 동기 requests 사용은 이벤트 루프를 블로킹할 수 있으므로 주의.
            # 실제 프로덕션에서는 비동기 HTTP 클라이언트 사용 권장.
            # 여기서는 기존 코드의 requests.post를 유지하되, 이 부분이 개선될 수 있음을 인지.
            response = await asyncio.to_thread(requests.post, self.api_url, headers=headers, json=payload)
            # import asyncio 필요
            
            if response.status_code != 200:
                error_content = response.text
                logger.error(f"OpenAI API 오류 (Job ID: {job_id}): {response.status_code} - {error_content}")
                self.jobs[job_id]["status"] = "error"
                self.jobs[job_id]["error_message"] = error_content
                return {
                    "success": False, 
                    "job_id": job_id,
                    "error": f"OpenAI API 실패: {error_content}"
                }

            response_data = response.json()
            images_list = []

            # 응답 데이터의 data 필드가 리스트인지 확인하고, 아니라면 리스트로 감싸서 처리
            data_items = response_data.get("data", [])
            if not isinstance(data_items, list):
                logger.warning(f"OpenAI API 응답의 'data' 필드가 리스트가 아닙니다. 단일 객체로 처리 시도. (Job ID: {job_id})")
                data_items = [data_items] if data_items else [] # 단일 객체이거나 None/empty일 경우 처리

            # logger.info(f"OpenAI API 응답 전체 (Job ID: {job_id}): {json.dumps(response_data, indent=2, ensure_ascii=False)}")

            for img_item in data_items:
                # logger.info(f"OpenAI API 이미지 아이템 (Job ID: {job_id}): {json.dumps(img_item, indent=2, ensure_ascii=False)}")
                image_info = {
                    "seed": None, # gpt-image-1은 seed를 명시적으로 반환하지 않음
                    "revised_prompt": img_item.get("revised_prompt")
                }
                
                # 오직 b64_json 필드만 확인하고 처리
                if "b64_json" in img_item and img_item["b64_json"]:
                    base64_data = img_item["b64_json"]
                    # 프론트엔드에서 바로 사용할 수 있도록 data URL 형식으로 만듦
                    image_info["url"] = f"data:image/png;base64,{base64_data}"
                    image_info["original_url"] = f"data:image/png;base64,{base64_data}" # 일관성을 위해 동일하게 설정
                    image_info["filename"] = f"openai_img_{uuid.uuid4()}.png" # 임의 파일명
                    image_info["is_base64"] = True # Base64 데이터임을 명시
                    logger.info(f"OpenAI 이미지 생성 성공 (b64_json 처리, Job ID: {job_id})")
                    images_list.append(image_info)
                else:
                    # b64_json이 없는 경우 경고 로깅하고 해당 아이템 건너뛰기
                    logger.warning(f"OpenAI 응답에 b64_json 데이터가 없습니다 (Job ID: {job_id}). 아이템: {img_item}")
                    continue # 다음 이미지 아이템으로
            
            if not images_list:
                logger.error(f"처리할 수 있는 이미지를 OpenAI 응답에서 찾지 못했습니다. (Job ID: {job_id})")
                self.jobs[job_id]["status"] = "error"
                self.jobs[job_id]["error_message"] = "OpenAI 응답에서 유효한 b64_json 이미지를 찾지 못함"
                return {
                    "success": False, 
                    "job_id": job_id,
                    "error": "OpenAI 응답에서 유효한 이미지를 찾지 못했습니다."
                }

            self.jobs[job_id]["status"] = "completed"
            self.jobs[job_id]["images"] = images_list
            self.jobs[job_id]["end_time"] = time.time()

            return {
                "success": True, 
                "job_id": job_id,
                "images": images_list, 
                "prompt": request_data.get("prompt", "")
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI API 요청 예외 (Job ID: {locals().get('job_id', 'N/A')}): {e}")
            if 'job_id' in locals():
                 self.jobs[job_id]["status"] = "error"
                 self.jobs[job_id]["error_message"] = str(e)
            return {"success": False, "error": f"OpenAI API 요청 실패: {str(e)}", "images": []}
        except Exception as e:
            logger.error(f"OpenAI 이미지 생성 중 일반 오류 (Job ID: {locals().get('job_id', 'N/A')}): {e}", exc_info=True)
            if 'job_id' in locals() and job_id in self.jobs:
                 self.jobs[job_id]["status"] = "error"
                 self.jobs[job_id]["error_message"] = str(e)
            return {"success": False, "error": f"이미지 생성 중 오류: {str(e)}", "images": []}

    async def get_status(self, job_id: str) -> Dict[str, Any]:
        """OpenAI 작업 상태 확인 (self.jobs에 저장된 정보 기반)"""
        job_info = self.jobs.get(job_id)
        if not job_info:
            return {
                "job_id": job_id,
                "status": "not_found",
                "message": "해당 Job ID를 찾을 수 없습니다."
            }
        
        response = {
            "job_id": job_id,
            "status": job_info.get("status", "unknown"),
            "message": f"Job status: {job_info.get('status', 'unknown')}"
        }
        if job_info.get("status") == "completed":
            response["images"] = job_info.get("images", [])
        elif job_info.get("status") == "error":
            response["error"] = job_info.get("error_message", "알 수 없는 오류")
        
        return response

# asyncio 임포트 추가 필요
import asyncio 