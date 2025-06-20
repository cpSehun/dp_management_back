"""
Persona 도메인 스키마
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime

class PersonaBase(BaseModel):
    """Persona 기본 스키마"""
    name: str = Field(..., description="페르소나 이름")
    type: str = Field(default="CHAR", description="페르소나 타입")
    status: str = Field(..., description="상태 (ACTIVE, INACTIVE)")
    
class PersonaCreate(PersonaBase):
    """Persona 생성 스키마"""
    id: Optional[str] = Field(None, description="페르소나 ID(UUID)")
    user_id: Optional[int] = Field(None, description="사용자 ID")
    model_id: Optional[str] = Field(None, description="모델 ID")
    tags: Optional[List[Any]] = Field(None, description="태그 리스트")
    properties: Optional[Dict[str, Any]] = Field(None, description="속성 정보")
    summary: Optional[str] = Field(None, max_length=100, description="30자 요약")
    llm_prompt: Optional[str] = Field(None, description="페르소나 정보 프롬프트")
    chat_opening: Optional[str] = Field(None, max_length=500, description="페르소나 시작멘트")
    background: Optional[str] = Field(None, max_length=1000, description="상태메시지(배경설정)")

class PersonaUpdate(BaseModel):
    """Persona 업데이트 스키마"""
    name: Optional[str] = Field(None, description="페르소나 이름")
    type: Optional[str] = Field(None, description="페르소나 타입")
    status: Optional[str] = Field(None, description="상태 (ACTIVE, INACTIVE)")
    user_id: Optional[int] = Field(None, description="사용자 ID")
    model_id: Optional[str] = Field(None, description="모델 ID")
    tags: Optional[List[Any]] = Field(None, description="태그 리스트")
    properties: Optional[Dict[str, Any]] = Field(None, description="속성 정보")
    summary: Optional[str] = Field(None, max_length=100, description="30자 요약")
    llm_prompt: Optional[str] = Field(None, description="페르소나 정보 프롬프트")
    chat_opening: Optional[str] = Field(None, max_length=500, description="페르소나 시작멘트")
    background: Optional[str] = Field(None, max_length=1000, description="상태메시지(배경설정)")

class Persona(PersonaBase):
    """Persona 응답 스키마"""
    seq: int = Field(..., description="시퀀스")
    id: Optional[str] = Field(None, description="페르소나 ID(UUID)")
    user_id: Optional[int] = Field(None, description="사용자 ID")
    model_id: Optional[str] = Field(None, description="모델 ID")
    tags: Optional[List[Any]] = Field(None, description="태그 리스트")
    properties: Optional[Dict[str, Any]] = Field(None, description="속성 정보")
    summary: Optional[str] = Field(None, description="30자 요약")
    llm_prompt: Optional[str] = Field(None, description="페르소나 정보 프롬프트")
    chat_opening: Optional[str] = Field(None, description="페르소나 시작멘트")
    background: Optional[str] = Field(None, description="상태메시지(배경설정)")
    created_at: Optional[datetime] = Field(None, description="등록 시각")
    updated_at: Optional[datetime] = Field(None, description="수정 시각")

    class Config:
        from_attributes = True  # SQLAlchemy 모델에서 자동 변환

class PersonaListResponse(BaseModel):
    """Persona 목록 응답 스키마"""
    total_items: int = Field(..., description="전체 항목 수")
    items: List[Persona] = Field(..., description="페르소나 목록")
    page: int = Field(default=1, description="현재 페이지")
    limit: int = Field(default=20, description="페이지당 항목 수")