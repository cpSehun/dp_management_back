from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
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

# 여기에 다른 모델(예: Prompt) 추가 가능
