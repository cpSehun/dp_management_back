"""
이미지 생성기 기본 클래스

모든 이미지 생성기가 구현해야 하는 기본 인터페이스를 정의합니다.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pathlib import Path
import os
import logging
import uuid

# 로깅 설정
logger = logging.getLogger(__name__)

# 기본 출력 디렉토리 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = Path('/app/output')

# 출력 디렉토리가 없으면 생성
if not OUTPUT_DIR.exists():
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"출력 디렉토리 생성 완료: {OUTPUT_DIR}")
    except Exception as e:
        logger.error(f"출력 디렉토리 생성 실패: {e}")

class ImageGenerator(ABC):
    """
    이미지 생성기 기본 클래스
    
    모든 이미지 생성기는 이 클래스를 상속받아 구현해야 합니다.
    """
    name: str = "base"
    description: str = "기본 이미지 생성기"
    
    def __init__(self):
        """이미지 생성기 초기화"""
        self.output_dir = OUTPUT_DIR
        
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
    
    def prepare_output_path(self, filename: str) -> Path:
        """
        출력 파일 경로 준비
        
        Args:
            filename: 파일명
            
        Returns:
            Path: 준비된 출력 파일 경로
        """
        filepath = self.output_dir / filename
        
        # 디렉토리 확인
        if not filepath.parent.exists():
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
        return filepath 