"""
도메인 모듈들의 통합 진입점
"""

# 각 도메인에서 라우터를 가져와서 메인 앱에 등록할 수 있도록 export
from .users import router as users_router
from .personas import router as personas_router
from .images import router as images_router
from .prompts import router as prompts_router

__all__ = [
    "users_router",
    "personas_router", 
    "images_router",
    "prompts_router"
]