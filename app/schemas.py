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
        from_attributes = True

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

# /generate 엔드포인트 전체 응답
class GenerateApiResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    generated_images: List[GeneratedImageInfo] = []
    error: Optional[str] = None

# ImageRequest 모델
class ImageRequest(BaseModel):
    prompt: str
    steps: int = 40
    batch_size: int = 1
    negative_prompt: Optional[str] = None
    width: Optional[int] = 1024
    height: Optional[int] = 1024
    guidance: Optional[float] = 3.5
    seed: Optional[int] = None
    model: Optional[str] = "flux-dev"

# --- ImagePromptVersion Schemas ---
class ImagePromptVersionBase(BaseModel):
    llm_prompt: str

class ImagePromptVersionCreate(ImagePromptVersionBase):
    pass

class ImagePromptVersionUpdate(BaseModel):
    llm_prompt: Optional[str] = None

class ImagePromptVersionInDB(ImagePromptVersionBase):
    id: int
    prompt_id: int
    version: int
    created_at: datetime
    created_by: Optional[int] = None

    class Config:
        from_attributes = True

# --- ImagePrompt Schemas ---
class ImagePromptBase(BaseModel):
    name: str
    llm_prompt: str

class ImagePromptCreate(ImagePromptBase):
    pass

class ImagePromptUpdate(BaseModel):
    name: Optional[str] = None
    llm_prompt: Optional[str] = None

class ImagePromptInDB(ImagePromptBase):
    id: int
    version: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None
    versions: List[ImagePromptVersionInDB] = []

    class Config:
        from_attributes = True

class ImagePromptResponse(ImagePromptInDB):
    pass

class PaginatedImagePromptsResponse(BaseModel):
    total_items: int
    items: List[ImagePromptResponse]

# --- PersonaPromptVersion Schemas ---
class PersonaPromptVersionBase(BaseModel):
    llm_prompt: str

class PersonaPromptVersionCreate(PersonaPromptVersionBase):
    pass

class PersonaPromptVersionUpdate(BaseModel):
    llm_prompt: Optional[str] = None

class PersonaPromptVersionInDB(PersonaPromptVersionBase):
    id: int
    prompt_id: int
    version: int
    created_at: datetime
    created_by: Optional[int] = None

    class Config:
        from_attributes = True

# --- PersonaPrompt Schemas ---
class PersonaPromptBase(BaseModel):
    name: str
    llm_prompt: str

class PersonaPromptCreate(PersonaPromptBase):
    pass

class PersonaPromptUpdate(BaseModel):
    name: Optional[str] = None
    llm_prompt: Optional[str] = None

class PersonaPromptInDB(PersonaPromptBase):
    id: int
    version: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None
    versions: List[PersonaPromptVersionInDB] = []

    class Config:
        from_attributes = True

class PersonaPromptResponse(PersonaPromptInDB):
    pass

class PaginatedPersonaPromptsResponse(BaseModel):
    total_items: int
    items: List[PersonaPromptResponse]