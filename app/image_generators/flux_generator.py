"""
Flux + ComfyUI 이미지 생성기

ComfyUI를 사용하여 Flux 워크플로우를 통해 이미지를 생성하는 구현체
"""
from typing import Dict, Any, List, Optional
import os
import json
import time
import requests
import logging
from pathlib import Path
from .base import ImageGenerator

# 로깅 설정
logger = logging.getLogger(__name__)

class FluxGenerator(ImageGenerator):
    """Flux + ComfyUI 이미지 생성기"""
    name = "flux-dev"
    description = "Flux + ComfyUI를 사용한 이미지 생성"
    
    def __init__(self):
        """Flux 이미지 생성기 초기화"""
        super().__init__()
        
        # 작업 디렉토리 설정 (워크플로우 파일 로드에 필요)
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.api_file = self.base_dir / 'flux1-dev-new.json' # 워크플로우 API 정의 파일
        
        # ComfyUI 서버 설정
        self.comfyui_server = os.getenv("COMFYUI_SERVER", "http://192.168.0.151:8188")
        
        # 로깅
        logger.info(f"Flux Generator 초기화 완료. ComfyUI 서버: {self.comfyui_server}")
        # self.output_dir 관련 로깅 및 설정 제거
    
    def get_comfyui_endpoint(self, path: str) -> str:
        """
        ComfyUI API 엔드포인트 URL 생성
        
        Args:
            path: API 경로
            
        Returns:
            str: 완성된 API URL
        """
        # URL이 http:// 또는 https://로 시작하는지 확인
        if self.comfyui_server.startswith(('http://', 'https://')):
            base_url = self.comfyui_server
        else:
            base_url = f"http://{self.comfyui_server}"
        
        # 경로가 /로 시작하는지 확인
        if path.startswith('/'):
            return f"{base_url}{path}"
        else:
            return f"{base_url}/{path}"
    
    def load_workflow(self) -> Dict:
        """
        워크플로우 파일 로드
        
        Returns:
            Dict: 로드된 워크플로우 데이터
        """
        try:
            with open(self.api_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"워크플로우 파일을 로드하는 중 오류 발생: {e}")
            raise ValueError(f"워크플로우 파일을 로드할 수 없습니다: {e}")
    
    def modify_workflow(self, workflow_data: Dict, request_data: Dict) -> Dict:
        """
        워크플로우 수정
        
        Args:
            workflow_data: 원본 워크플로우 데이터
            request_data: 요청 데이터
            
        Returns:
            Dict: 수정된 워크플로우 데이터
        """
        try:
            # 워크플로우 복사본 생성
            modified_workflow = workflow_data.copy()
            
            # 텍스트 프롬프트 수정 (positive prompt)
            if "6" in modified_workflow:  # CLIP Text Encode (Positive Prompt) 노드
                modified_workflow["6"]["inputs"]["text"] = request_data.get("prompt", "")
            
            # 이미지 크기 및 배치 크기 설정
            if "27" in modified_workflow:  # Empty Latent Image 노드
                modified_workflow["27"]["inputs"]["width"] = request_data.get("width", 1024)
                modified_workflow["27"]["inputs"]["height"] = request_data.get("height", 1024)
                modified_workflow["27"]["inputs"]["batch_size"] = request_data.get("batch_size", 1)
            
            # 가이던스 스케일 설정
            if "26" in modified_workflow:  # FluxGuidance 노드
                modified_workflow["26"]["inputs"]["guidance"] = request_data.get("guidance", 3.5)
            
            # 스텝 수 설정
            if "17" in modified_workflow:  # BasicScheduler 노드
                modified_workflow["17"]["inputs"]["steps"] = request_data.get("steps", 40)
            
            # 시드 설정
            if "25" in modified_workflow and request_data.get("seed") is not None:  # RandomNoise 노드
                modified_workflow["25"]["inputs"]["noise_seed"] = request_data.get("seed")
            
            # 부정 프롬프트 설정 (있다면)
            if "7" in modified_workflow and request_data.get("negative_prompt") is not None:
                modified_workflow["7"]["inputs"]["text"] = request_data.get("negative_prompt", "")
            
            return modified_workflow
        except Exception as e:
            logger.error(f"워크플로우 수정 중 오류 발생: {e}")
            raise ValueError(f"워크플로우 수정 중 오류: {e}")
    
    async def send_workflow_to_comfyui(self, workflow_data: Dict) -> Dict:
        """
        ComfyUI로 워크플로우 전송
        
        Args:
            workflow_data: 워크플로우 데이터
            
        Returns:
            Dict: ComfyUI API 응답
        """
        try:
            url = self.get_comfyui_endpoint("api/prompt")
            logger.info(f"ComfyUI API 요청 URL: {url}")
            response = requests.post(url, json={"prompt": workflow_data})
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"ComfyUI API 오류: {response.status_code} - {response.text}")
                raise ValueError(f"ComfyUI API 오류: {response.text}")
        except requests.RequestException as e:
            logger.error(f"ComfyUI API 요청 중 오류 발생: {e}")
            raise ValueError(f"ComfyUI API 요청 중 오류: {e}")
    
    async def wait_for_job_completion(self, job_id: str, max_retries=120) -> Optional[Dict]:
        """
        이미지 생성 작업이 완료될 때까지 대기
        
        Args:
            job_id: 작업 ID
            max_retries: 최대 시도 횟수
            
        Returns:
            Optional[Dict]: 작업 완료 결과 또는 None
        """
        for i in range(max_retries):
            try:
                url = self.get_comfyui_endpoint(f"api/history/{job_id}")
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
            url = self.get_comfyui_endpoint(f"api/history/{job_id}")
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
    
    async def download_comfyui_images(self, job_id: str, results: Dict) -> List[Dict]:
        """
        ComfyUI에서 생성된 이미지 정보를 반환 (로컬 저장 안 함)
        
        Args:
            job_id: 작업 ID
            results: 작업 결과 데이터
            
        Returns:
            List[Dict]: ComfyUI 원본 이미지 정보 목록 (URL 포함)
        """
        returned_images = []
        
        try:
            if not results:
                logger.error(f"결과가 없습니다: {job_id}")
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
                logger.info(f"outputs 필드 없음, API 재호출: {job_id}")
                url = self.get_comfyui_endpoint(f"api/history/{job_id}")
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
                        logger.error(f"outputs 필드를 찾을 수 없어 이미지를 가져올 수 없습니다: {job_id}")
                        return returned_images
                else:
                    logger.error(f"API 재호출 실패: {response.status_code} - {job_id}")
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
                        
                        img_url = self.get_comfyui_endpoint(f"view?filename={comfy_filename}&subfolder={comfy_subfolder}&type={comfy_type}")
                        logger.debug(f"ComfyUI 원본 이미지 URL: {img_url}")
                        
                        returned_images.append({
                            # "url" 필드는 이제 original_url과 동일하게 ComfyUI 직접 URL을 가리킴
                            "url": img_url, 
                            "filename": comfy_filename, # ComfyUI가 제공하는 파일명
                            "original_url": img_url,
                            "node_id": node_id,
                            "node_type": node_types.get(node_id, "Unknown"),
                            "subfolder": comfy_subfolder,
                            "type": comfy_type
                        })
                        logger.info(f"ComfyUI 이미지 정보 추가: {i+1}/{len(images_data)} - {comfy_filename}")
        
        except Exception as e:
            logger.error(f"ComfyUI 이미지 정보 처리 중 오류: {e}, job_id: {job_id}")
        
        return returned_images
    
    async def generate(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        이미지 생성 메서드
        
        Args:
            request_data: 이미지 생성 요청 데이터
            
        Returns:
            Dict[str, Any]: 생성된 이미지 정보를 포함한 응답
        """
        try:
            # save_to_backend 파라미터 관련 로직 제거
            # logger.info(f"요청 데이터 (save_to_backend 생략): {request_data}")

            workflow_data = self.load_workflow()
            modified_workflow = self.modify_workflow(workflow_data, request_data)
            
            response = await self.send_workflow_to_comfyui(modified_workflow)
            
            if not response:
                return {
                    "success": False,
                    "error": "이미지 생성 요청이 실패했습니다"
                }
            
            # job_id 가져오기
            job_id = self.generate_job_id()
            if "prompt_id" in response:
                job_id = response["prompt_id"]
                logger.info(f"작업 ID: {job_id}")
            
            # 이미지 생성 완료 대기
            results = await self.wait_for_job_completion(job_id)
            
            if not results:
                return {
                    "success": False,
                    "error": "이미지 생성 시간이 초과되었습니다"
                }
            
            # 이미지 다운로드 및 저장 (save_to_backend 파라미터 전달 부분 삭제)
            images = await self.download_comfyui_images(job_id, results)
            
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
    
    async def get_status(self, job_id: str) -> Dict[str, Any]:
        """
        작업 상태 확인
        
        Args:
            job_id: 작업 ID
            
        Returns:
            Dict[str, Any]: 작업 상태 정보
        """
        try:
            # ComfyUI API에서 작업 상태 확인
            url = self.get_comfyui_endpoint(f"api/history/{job_id}")
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