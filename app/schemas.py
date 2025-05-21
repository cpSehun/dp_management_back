from pydantic import BaseModel, EmailStr, Field, HttpUrl
from typing import Optional, List
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
        from_attributes = True  # Pydantic v2 스타일

# 로그인 요청 스키마 (추후 로그인 기능 구현 시 사용)
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class GeneratedImageBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="이미지 이름")
    prompt: Optional[str] = Field(None, description="이미지 생성에 사용된 프롬프트")
    negative_prompt: Optional[str] = Field(None, description="네거티브 프롬프트")
    model: Optional[str] = Field(None, description="사용된 모델")
    s3_url: HttpUrl = Field(..., description="S3에 저장된 이미지 URL")
    width: Optional[int] = Field(None, description="이미지 가로 크기")
    height: Optional[int] = Field(None, description="이미지 세로 크기")
    steps: Optional[int] = Field(None, description="생성 스텝 수")
    guidance: Optional[float] = Field(None, description="가이던스 값")
    seed: Optional[int] = Field(None, description="시드 값")
    user_id: Optional[int] = Field(None, description="생성한 사용자 ID (해당되는 경우)")

class GeneratedImageCreate(GeneratedImageBase):
    pass

class GeneratedImageResponse(GeneratedImageBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

# /generate 엔드포인트 응답 내 이미지 정보
class GeneratedImageInfo(BaseModel):
    s3_url: HttpUrl = Field(..., description="S3에 업로드된 이미지의 URL")
    original_filename: Optional[str] = Field(None, description="ComfyUI에서 생성된 원본 파일명")
    prompt: str
    steps: int
    batch_size: int
    negative_prompt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    guidance: Optional[float] = None
    seed: Optional[int] = None
    model: Optional[str] = None
    
    # 사용자가 이미지 저장 시 이름을 설정할 수 있도록 원본 요청 정보 전달
    # 프론트엔드에서 이 정보를 사용하여 'GeneratedImageCreate' 요청을 구성할 수 있음


# /generate 엔드포인트 전체 응답
class GenerateApiResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    generated_images: List[GeneratedImageInfo] = []
    error: Optional[str] = None

# ImageRequest 모델 (기존 image_generator.py 에서 가져와 save_to_backend 필드 제거)
class ImageRequest(BaseModel):
    prompt: str
    steps: int = 40
    batch_size: int = 1
    negative_prompt: Optional[str] = None
    width: Optional[int] = 1024
    height: Optional[int] = 1024
    guidance: Optional[float] = 3.5
    seed: Optional[int] = None
    model: Optional[str] = "flux-dev" # 기본값은 flux-dev 