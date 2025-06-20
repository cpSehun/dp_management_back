"""
공통 의존성 함수들
"""
from fastapi import Depends
from app.security import get_current_active_user
from app import models

# 공통 의존성을 재사용 가능하도록 래핑
def get_current_active_user_dep() -> models.User:
    """현재 활성 사용자 의존성"""
    return Depends(get_current_active_user)