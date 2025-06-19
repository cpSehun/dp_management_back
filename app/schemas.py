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

# --- GeneratedImage Schemas (새로 추가) ---
class GeneratedImageBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="이미지 이름")
    prompt: str = Field(..., description="이미지 생성에 사용된 프롬프트")
    model: str = Field(..., description="사용된 모델")
    s3_url: str = Field(..., description="S3에 저장된 이미지 URL")
    tags: Optional[str] = Field(None, description="태그 (쉼표로 구분)")
    steps: Optional[int] = Field(None, description="생성 스텝 수 (flux-dev만)")
    seed: Optional[int] = Field(None, description="시드 값 (flux-dev만)")

class GeneratedImageCreate(GeneratedImageBase):
    pass

class GeneratedImageInDB(GeneratedImageBase):
    id: int
    created_at: datetime
    created_by: Optional[str] = None  # username으로 변환되어 전달

    class Config:
        from_attributes = True

class GeneratedImageResponse(GeneratedImageInDB):
    pass

class PaginatedGeneratedImagesResponse(BaseModel):
    total_items: int
    items: List[GeneratedImageResponse]

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
    created_by: Optional[str] = None

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
    created_by: Optional[str] = None
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
    created_by: Optional[str] = None

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
    created_by: Optional[str] = None
    versions: List[PersonaPromptVersionInDB] = []

    class Config:
        from_attributes = True

class PersonaPromptResponse(PersonaPromptInDB):
    pass

class PaginatedPersonaPromptsResponse(BaseModel):
    total_items: int
    items: List[PersonaPromptResponse]
    

############################### persona 생성 관련 ###############################

# WorkflowPromptVersion 스키마
class WorkflowPromptVersionBase(BaseModel):
    version: int
    llm_prompt: str

class WorkflowPromptVersionCreate(WorkflowPromptVersionBase):
    pass

class WorkflowPromptVersion(WorkflowPromptVersionBase):
    id: int
    prompt_id: int
    created_at: datetime
    created_by: Optional[int] = None

    class Config:
        from_attributes = True

# WorkflowPrompt 스키마
class WorkflowPromptBase(BaseModel):
    name: str
    category: str  # concept, persona_info, summary, tags, image
    type: Optional[str] = None  # CHAR, STORY, NULL
    llm_prompt: str

class WorkflowPromptCreate(WorkflowPromptBase):
    pass

class WorkflowPromptUpdate(BaseModel):
    name: Optional[str] = None
    llm_prompt: Optional[str] = None

class WorkflowPrompt(WorkflowPromptBase):
    id: int
    version: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    versions: List[WorkflowPromptVersion] = []

    class Config:
        from_attributes = True

# 페이지네이션 응답
class PaginatedWorkflowPrompts(BaseModel):
    total_items: int
    items: List[WorkflowPrompt]

# 최신 프롬프트 조회용 스키마
class LatestPromptRequest(BaseModel):
    category: str
    type: Optional[str] = None

class LatestPromptResponse(BaseModel):
    id: int
    name: str
    category: str
    type: Optional[str] = None
    llm_prompt: str
    version: int