"""
이미지 생성기 기본 클래스

모든 이미지 생성기가 구현해야 하는 기본 인터페이스를 정의합니다.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import uuid
# from pathlib import Path # Path 임포트는 더 이상 필요 없음
import logging

# 로깅 설정
logger = logging.getLogger(__name__)

# OUTPUT_DIR = Path(__file__).resolve().parent.parent / 'output' # 더 이상 사용하지 않음

class ImageGenerator(ABC):
    """
    이미지 생성기 기본 클래스
    
    모든 이미지 생성기는 이 클래스를 상속받아 구현해야 합니다.
    """
    name: str = "base"
    description: str = "기본 이미지 생성기"
    
    def __init__(self):
        """이미지 생성기 초기화"""
        # self.output_dir = OUTPUT_DIR # 이 줄을 제거하거나 주석 처리
        # if not self.output_dir.exists(): # 관련 디렉토리 생성 로직도 제거
        #     self.output_dir.mkdir(parents=True, exist_ok=True)
        pass
    
    @abstractmethod
    async def generate(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        이미지 생성 메서드
        
        Args:
            request_data: 이미지 생성 요청 데이터
            
        Returns:
            Dict[str, Any]: 생성된 이미지 정보를 포함한 응답
        """
        pass
    
    @abstractmethod
    async def get_status(self, job_id: str) -> Dict[str, Any]:
        """
        작업 상태 확인
        
        Args:
            job_id: 작업 ID
            
        Returns:
            Dict[str, Any]: 작업 상태 정보
        """
        pass

    def get_model_info(self) -> Dict[str, Any]:
        """
        모델 정보 반환
        
        Returns:
            Dict[str, Any]: 모델 이름, 설명 등의 정보
        """
        return {
            "name": self.name,
            "description": self.description
        }
        
    def generate_job_id(self) -> str:
        """
        고유한 작업 ID 생성
        
        Returns:
            str: 생성된 작업 ID
        """
        return str(uuid.uuid4())
    
    # prepare_output_path 메소드 삭제
    # def prepare_output_path(self, filename: str) -> Path:
    #     """
    #     출력 파일 경로 준비
    #     
    #     Args:
    #         filename: 파일명
    #         
    #     Returns:
    #         Path: 준비된 출력 파일 경로
    #     """
    #     filepath = self.output_dir / filename
    #     
    #     # 디렉토리 확인
    #     if not filepath.parent.exists():
    #         filepath.parent.mkdir(parents=True, exist_ok=True)
    #         
    #     return filepath 