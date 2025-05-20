"""
이미지 생성기 팩토리

다양한 이미지 생성 모델에 대한 인스턴스를 관리하고 제공하는 팩토리 클래스
"""
import logging
from typing import Dict, List, Type, Optional
from .base import ImageGenerator
from .flux_generator import FluxGenerator
from .gpt_generator import GptImageGenerator

# 로깅 설정
logger = logging.getLogger(__name__)

class ImageGeneratorFactory:
    """이미지 생성기 팩토리 클래스"""
    
    _generators: Dict[str, ImageGenerator] = {}
    _generator_classes: Dict[str, Type[ImageGenerator]] = {
        "flux-dev": FluxGenerator,
        "gpt-image-1": GptImageGenerator
    }
    
    @classmethod
    def get_generator(cls, generator_name: str) -> Optional[ImageGenerator]:
        """
        지정된 이름의 이미지 생성기 인스턴스 반환
        
        Args:
            generator_name: 이미지 생성기 이름
            
        Returns:
            Optional[ImageGenerator]: 이미지 생성기 인스턴스 또는 None
        """
        # 이미 생성된 인스턴스가 있으면 재사용
        if generator_name in cls._generators:
            return cls._generators[generator_name]
        
        # 새 인스턴스 생성
        if generator_name in cls._generator_classes:
            try:
                generator = cls._generator_classes[generator_name]()
                cls._generators[generator_name] = generator
                logger.info(f"이미지 생성기 생성: {generator_name}")
                return generator
            except Exception as e:
                logger.error(f"이미지 생성기 생성 오류: {generator_name} - {e}")
                return None
        
        # 지원하지 않는 생성기
        logger.warning(f"지원하지 않는 이미지 생성기: {generator_name}")
        return None
    
    @classmethod
    def list_generators(cls) -> List[Dict[str, str]]:
        """
        사용 가능한 이미지 생성기 목록 반환
        
        Returns:
            List[Dict[str, str]]: 이미지 생성기 정보 목록
        """
        generators = []
        
        for generator_name, generator_class in cls._generator_classes.items():
            try:
                # 인스턴스가 없으면 임시로 생성하여 정보 가져오기
                if generator_name not in cls._generators:
                    generator = generator_class()
                else:
                    generator = cls._generators[generator_name]
                
                # 생성기 정보 추가
                generators.append({
                    "name": generator.name,
                    "description": generator.description
                })
            except Exception as e:
                logger.error(f"생성기 정보 가져오기 오류: {generator_name} - {e}")
                # 오류가 발생해도 기본 정보라도 추가
                generators.append({
                    "name": generator_name,
                    "description": f"{generator_name} 이미지 생성기"
                })
        
        return generators
    
    @classmethod
    def register_generator(cls, name: str, generator_class: Type[ImageGenerator]) -> bool:
        """
        새로운 이미지 생성기 클래스 등록
        
        Args:
            name: 이미지 생성기 이름
            generator_class: 이미지 생성기 클래스
            
        Returns:
            bool: 등록 성공 여부
        """
        if not issubclass(generator_class, ImageGenerator):
            logger.error(f"등록 실패: {name} - ImageGenerator의 서브클래스가 아님")
            return False
        
        cls._generator_classes[name] = generator_class
        logger.info(f"이미지 생성기 등록: {name}")
        return True 