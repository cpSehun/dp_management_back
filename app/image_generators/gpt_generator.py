"""
OpenAI GPT-4 Vision (gpt-image-1) 이미지 생성기

OpenAI의 이미지 생성 모델을 사용하여 이미지를 생성하는 구현체
"""
from typing import Dict, Any, List, Optional
import os
import json
import time
import requests
import logging
import base64
from pathlib import Path
from .base import ImageGenerator
import uuid

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
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY가 설정되지 않았습니다. 환경 변수를 확인하세요.")
        
        # API 엔드포인트 설정
        self.api_url = "https://api.openai.com/v1/images/generations"
        
        # 진행 중인 작업 추적
        self.jobs = {}
        
        # 로깅
        logger.info(f"GPT Image Generator 초기화")
    
    async def generate(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        이미지 생성 메서드
        
        Args:
            request_data: 이미지 생성 요청 데이터
            
        Returns:
            Dict[str, Any]: 생성된 이미지 정보를 포함한 응답
        """
        try:
            # 백엔드 저장 여부 확인
            save_to_backend = request_data.get("save_to_backend", True)
            
            # API 키 확인
            if not self.api_key:
                return {
                    "success": False,
                    "error": "OpenAI API 키가 설정되지 않았습니다. 환경 변수를 확인하세요."
                }
            
            # 작업 ID 생성
            job_id = self.generate_job_id()
            
            # GPT-image-1 모델용 요청 데이터 준비 (공식 예제에 따름)
            # https://platform.openai.com/docs/guides/image-generation?image-generation-model=gpt-image-1 참조
            openai_request = {
                "model": "gpt-image-1",
                "prompt": request_data.get("prompt", ""),
                "n": request_data.get("batch_size", 1),  # 생성할 이미지 수
                "size": "1024x1024"  # gpt-image-1은 현재 1024x1024만 지원
            }
            
            # 음성 프롬프트 추가 (있는 경우)
            if request_data.get("negative_prompt"):
                openai_request["prompt"] += f"\nDo not include: {request_data.get('negative_prompt')}"
            
            logger.info(f"OpenAI 요청 준비: {job_id}")
            logger.info(f"요청 데이터: {json.dumps(openai_request, ensure_ascii=False)}")
            
            # 작업 상태 설정
            self.jobs[job_id] = {
                "status": "processing",
                "request": openai_request,
                "start_time": time.time()
            }
            
            # API 요청 보내기
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=openai_request
            )
            
            # 응답 처리
            if response.status_code != 200:
                logger.error(f"OpenAI API 오류: {response.status_code} - {response.text}")
                self.jobs[job_id]["status"] = "error"
                self.jobs[job_id]["error"] = response.text
                
                return {
                    "success": False,
                    "job_id": job_id,
                    "error": f"이미지 생성 요청이 실패했습니다: {response.text}"
                }
            
            # 응답 데이터 파싱
            response_data = response.json()
            # 중요 구조만 로깅
            response_structure = {
                "keys": list(response_data.keys())
            }
            if "data" in response_data:
                response_structure["data_count"] = len(response_data["data"])
                if response_data["data"] and len(response_data["data"]) > 0:
                    response_structure["data_keys"] = list(response_data["data"][0].keys())
            
            logger.info(f"OpenAI 응답 구조: {json.dumps(response_structure, ensure_ascii=False)}")
            
            # 'data' 필드 확인
            if "data" not in response_data or not response_data["data"]:
                logger.error(f"응답에 'data' 필드가 없거나 비어있습니다")
                return {
                    "success": False,
                    "job_id": job_id,
                    "error": "API 응답에 이미지 데이터가 없습니다"
                }
            
            # 이미지 저장
            images = []
            for i, image_data in enumerate(response_data.get("data", [])):
                try:
                    # 응답 유형 확인 (URL 또는 b64_json)
                    logger.info(f"이미지 {i} 데이터 키: {list(image_data.keys()) if isinstance(image_data, dict) else '객체 속성'}")

                    # b64_json 필드가 있는지 확인
                    image_b64 = None
                    if hasattr(image_data, "b64_json") and image_data.b64_json:
                        image_b64 = image_data.b64_json
                    elif isinstance(image_data, dict) and "b64_json" in image_data:
                        image_b64 = image_data["b64_json"]

                    if image_b64:
                        logger.info(f"이미지 {i}에서 b64_json 데이터 발견 (길이: {len(image_b64)})")
                        
                        # 백엔드에 저장하지 않는 경우, Base64 데이터를 그대로 반환
                        if not save_to_backend:
                            images.append({
                                "url": f"data:image/png;base64,{image_b64}",
                                "filename": f"gpt_image_{i}.png",
                                "is_base64": True
                            })
                            logger.info(f"Base64 이미지 추가 (저장하지 않음): {i+1}/{len(response_data.get('data', []))}")
                            continue
                        
                        # 백엔드에 저장하는 경우
                        try:
                            # Base64 디코딩
                            image_data_bytes = base64.b64decode(image_b64)
                            
                            # 파일명 생성 및 저장
                            filename = f"gpt_{uuid.uuid4()}.png"
                            filepath = self.output_dir / filename
                            
                            # 디렉토리 확인
                            if not filepath.parent.exists():
                                filepath.parent.mkdir(parents=True, exist_ok=True)
                            
                            # 파일 저장
                            with open(filepath, "wb") as f:
                                f.write(image_data_bytes)
                            
                            # 이미지 정보 추가
                            image_info = {
                                "url": f"/api/v1/image-generator/outputs/{filename}",
                                "filename": f"generated_image_{filename}"
                            }
                            
                            # revised_prompt가 있으면 추가
                            if isinstance(image_data, dict) and "revised_prompt" in image_data:
                                image_info["revised_prompt"] = image_data["revised_prompt"]
                            
                            images.append(image_info)
                            logger.info(f"Base64 이미지 저장 완료: {filepath}")
                        except Exception as e:
                            logger.error(f"Base64 이미지 저장 중 오류: {e}")
                        
                        continue

                    # URL 형식으로 반환된 경우
                    image_url = None
                    
                    # URL 필드 확인 (url 또는 image_url)
                    if hasattr(image_data, "url") and image_data.url:
                        image_url = image_data.url
                    elif hasattr(image_data, "image_url") and image_data.image_url:
                        image_url = image_data.image_url
                    # 딕셔너리 형태로 반환된 경우도 처리
                    elif isinstance(image_data, dict):
                        image_url = image_data.get("url") or image_data.get("image_url")
                    
                    # URL이 없는 경우 http:// 로 시작하는 문자열 찾기 시도
                    if not image_url and isinstance(image_data, dict):
                        for key, value in image_data.items():
                            if isinstance(value, str) and value.startswith("http://") or value.startswith("https://"):
                                image_url = value
                                logger.info(f"대체 URL 필드 '{key}' 발견: {value}")
                                break
                    
                    if not image_url:
                        logger.warning(f"이미지 {i}에 URL 데이터가 없습니다")
                        continue
                    
                    # 백엔드에 저장하지 않는 경우, OpenAI URL을 직접 반환
                    if not save_to_backend:
                        images.append({
                            "url": image_url,
                            "filename": f"gpt_image_{i}.png",
                            "original_url": image_url
                        })
                        logger.info(f"이미지 URL 추가 (저장하지 않음): {i+1}/{len(response_data.get('data', []))} - {image_url}")
                        continue
                    
                    # 백엔드에 저장하는 경우
                    try:
                        # 이미지 다운로드 및 저장
                        img_response = requests.get(image_url, stream=True)
                        
                        if img_response.status_code == 200:
                            # 파일명 생성
                            filename = f"gpt_{uuid.uuid4()}.png"
                            filepath = self.output_dir / filename
                            
                            # 디렉토리 확인
                            if not filepath.parent.exists():
                                filepath.parent.mkdir(parents=True, exist_ok=True)
                            
                            # 파일 저장
                            with open(filepath, 'wb') as f:
                                for chunk in img_response.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            
                            # 이미지 정보 추가
                            image_info = {
                                "url": f"/api/v1/image-generator/outputs/{filename}",
                                "filename": f"generated_image_{filename}",
                                "original_url": image_url  # 원본 URL도 추가
                            }
                            
                            images.append(image_info)
                            logger.info(f"이미지 저장 완료: {filepath}")
                        else:
                            logger.error(f"이미지 다운로드 실패: {img_response.status_code}")
                    except Exception as e:
                        logger.error(f"이미지 저장 중 오류: {e}")
                    
                except Exception as e:
                    logger.error(f"이미지 저장 중 오류: {e}")
            
            # 생성된 이미지가 없는 경우
            if not images:
                logger.error("생성된 이미지가 없습니다")
                return {
                    "success": False,
                    "job_id": job_id,
                    "error": "이미지 생성에 실패했습니다"
                }
            
            # 작업 완료 표시
            self.jobs[job_id]["status"] = "completed"
            self.jobs[job_id]["images"] = images
            self.jobs[job_id]["end_time"] = time.time()
            
            # 결과 반환
            return {
                "success": True,
                "job_id": job_id,
                "images": images,
                "message": "이미지 생성이 완료되었습니다"
            }
            
        except Exception as e:
            logger.error(f"이미지 생성 오류: {e}")
            
            # 작업 ID가 있으면 상태 업데이트
            if 'job_id' in locals():
                self.jobs[job_id]["status"] = "error"
                self.jobs[job_id]["error"] = str(e)
            
            return {
                "success": False,
                "error": f"이미지 생성 중 오류가 발생했습니다: {str(e)}"
            }
    
    async def get_status(self, job_id: str) -> Dict[str, Any]:
        """
        작업 상태 확인
        
        Args:
            job_id: 작업 ID
            
        Returns:
            Dict[str, Any]: 작업 상태 정보
        """
        # 작업 정보 확인
        job_info = self.jobs.get(job_id)
        
        if not job_info:
            return {
                "job_id": job_id,
                "status": "not_found",
                "message": "작업을 찾을 수 없습니다"
            }
        
        # 상태 반환
        return {
            "job_id": job_id,
            "status": job_info.get("status", "unknown"),
            "images": job_info.get("images", []) if job_info.get("status") == "completed" else [],
            "error": job_info.get("error") if job_info.get("status") == "error" else None
        } 