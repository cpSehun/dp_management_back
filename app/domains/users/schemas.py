"""
User 도메인 스키마 
기존 app/schemas.py에서 User 관련 부분을 이동
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

# 공통 속성을 위한 기본 스키마
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None

# 사용자 생성을 위한 스키마 (UserBase 상속, 비밀번호 추가)
class UserCreate(UserBase):
    password: str

# 데이터베이스에서 읽어올 때 또는 API 응답으로 사용될 스키마 (비밀번호 제외)
class User(UserBase):
    id: int
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# 로그인 요청 스키마
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str