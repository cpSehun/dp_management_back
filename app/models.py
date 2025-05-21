from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    """
    사용자 정보를 저장하는 SQLAlchemy 모델.
    """
    __tablename__ = "users" # 데이터베이스 테이블 이름

    id = Column(Integer, primary_key=True, index=True, autoincrement=True) # 사용자 고유 ID
    username = Column(String(50), unique=True, index=True, nullable=False) # 사용자 이름 (로그인 ID)
    email = Column(String(100), unique=True, index=True, nullable=False) # 이메일
    hashed_password = Column(String(255), nullable=False) # 해싱된 비밀번호
    full_name = Column(String(100), nullable=True) # 전체 이름
    is_active = Column(Boolean, default=True) # 계정 활성 상태
    is_superuser = Column(Boolean, default=False) # 관리자 여부
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # 생성 일시
    updated_at = Column(DateTime(timezone=True), onupdate=func.now()) # 수정 일시

    # 관계 설정
    generated_images = relationship("GeneratedImage", back_populates="user")

class GeneratedImage(Base):
    """
    생성된 이미지 정보를 저장하는 SQLAlchemy 모델
    """
    __tablename__ = "generated_images"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)  # 이미지 이름
    prompt = Column(Text, nullable=True)  # 이미지 생성에 사용된 프롬프트
    negative_prompt = Column(Text, nullable=True)  # 네거티브 프롬프트
    model = Column(String(100), nullable=True)  # 사용된 모델
    s3_url = Column(String(1024), nullable=False)  # S3에 저장된 이미지 URL
    width = Column(Integer, nullable=True)  # 이미지 가로 크기
    height = Column(Integer, nullable=True)  # 이미지 세로 크기
    steps = Column(Integer, nullable=True)  # 생성 스텝 수
    guidance = Column(Float, nullable=True)  # 가이던스 값
    seed = Column(Integer, nullable=True)  # 시드 값
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # 생성한 사용자 ID
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # 생성 일시
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())  # 수정 일시
    
    # 관계 설정
    user = relationship("User", back_populates="generated_images")

# 여기에 다른 모델(예: Prompt) 추가 가능
