from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float, BigInteger, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, declarative_mixin, declared_attr
from app.database import Base

# User 클래스는 app/domains/users/models.py로 이동했으므로 여기서 제거
# User 모델이 필요한 관계 설정을 위해 import
from app.domains.users.models import User

class GeneratedImage(Base):
    """
    생성된 이미지 정보를 저장하는 SQLAlchemy 모델
    """
    __tablename__ = "generated_images"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)  # 이미지 이름
    prompt = Column(Text, nullable=False)  # 생성 프롬프트
    model = Column(String(100), nullable=False)  # 사용 모델 (flux-dev, gpt-image-1 등)
    s3_url = Column(String(1024), nullable=False)  # S3 저장 URL
    tags = Column(Text, nullable=True)  # 태그 (쉼표로 구분된 문자열)
    steps = Column(Integer, nullable=True)  # 생성 스텝 (flux-dev만 해당)
    seed = Column(BigInteger, nullable=True)  # 시드값 (BigInteger로 변경 - 큰 수 지원)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계 설정 - 기존 이름 사용
    user = relationship("User", back_populates="generated_images")
    
############################### persona 생성 관련 ###############################

class WorkflowPrompt(Base):
    __tablename__ = "workflow_prompts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(50), nullable=False)
    type = Column(String(10), nullable=True, index=True)  # CHAR, STORY, NULL
    llm_prompt = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)  # 현재 활성 버전 번호
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 관계 설정
    versions = relationship("WorkflowPromptVersion", back_populates="prompt", cascade="all, delete-orphan")
    created_by_user = relationship("User", back_populates="workflow_prompts")
    
    # type만으로 인덱스 생성
    __table_args__ = (
        Index('idx_workflow_type', 'type'),
    )

class WorkflowPromptVersion(Base):
    __tablename__ = "workflow_prompt_versions"

    id = Column(Integer, primary_key=True, index=True)
    prompt_id = Column(Integer, ForeignKey("workflow_prompts.id"), nullable=False)
    version = Column(Integer, nullable=False)
    llm_prompt = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # 관계 설정
    prompt = relationship("WorkflowPrompt", back_populates="versions")
    created_by_user = relationship("User", back_populates="workflow_prompt_versions")