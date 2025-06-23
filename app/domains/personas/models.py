"""
Persona 도메인 모델
외부 DB t_persona 테이블 매핑
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.domains.personas.database import PersonaBase

class TPersona(PersonaBase):
    """
    외부 DB의 t_persona 테이블 모델
    """
    __tablename__ = "t_persona"

    seq = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    type = Column(String(10), nullable=False, default="CHAR", index=True)  # CHAR, STORY
    status = Column(String(10), nullable=False, default="ACTIVE", index=True)  # ACTIVE, INACTIVE
    id = Column(String(255), nullable=True, index=True)  # UUID
    user_id = Column(Integer, nullable=True)
    model_id = Column(String(255), nullable=True)
    tags = Column(JSON, nullable=True)  # JSON 배열
    properties = Column(JSON, nullable=True)  # JSON 객체
    summary = Column(String(100), nullable=True)  # 30자 요약
    llm_prompt = Column(Text, nullable=True)  # 페르소나 정보 프롬프트
    chat_opening = Column(String(500), nullable=True)  # 페르소나 시작멘트
    background = Column(String(1000), nullable=True)  # 상태메시지(배경설정)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<TPersona(seq={self.seq}, name='{self.name}', type='{self.type}')>"