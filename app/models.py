from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float, BigInteger, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, declarative_mixin, declared_attr
from app.database import Base

class User(Base):
    """
    사용자 정보를 저장하는 SQLAlchemy 모델.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=False)  # 기본값을 False로 변경
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 관계 설정 - 기존 이름 사용
    generated_images = relationship("GeneratedImage", back_populates="user")
    image_prompts = relationship("ImagePrompt", back_populates="created_by_user")
    persona_prompts = relationship("PersonaPrompt", back_populates="created_by_user")
    
    # 새로 추가할 relationships
    workflow_prompts = relationship("WorkflowPrompt", back_populates="created_by_user")
    workflow_prompt_versions = relationship("WorkflowPromptVersion", back_populates="created_by_user")

class GeneratedImage(Base):
    """
    생성된 이미지 정보를 저장하는 SQLAlchemy 모델 (ImagePrompt 참고하여 재설계)
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

class ImagePrompt(Base):
    __tablename__ = "image_prompts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)
    llm_prompt = Column(Text, nullable=False)  # image_prompt에서 변경
    version = Column(Integer, nullable=False)  # 현재 활성 버전 번호 추가
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 관계 설정
    versions = relationship("ImagePromptVersion", back_populates="prompt", cascade="all, delete-orphan")
    created_by_user = relationship("User", back_populates="image_prompts")
    
class ImagePromptVersion(Base):
    __tablename__ = "image_prompt_versions"

    id = Column(Integer, primary_key=True, index=True)
    prompt_id = Column(Integer, ForeignKey("image_prompts.id"), nullable=False)
    version = Column(Integer, nullable=False)
    llm_prompt = Column(Text, nullable=False)  # content에서 변경
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # 관계 설정
    prompt = relationship("ImagePrompt", back_populates="versions")
    created_by_user = relationship("User", foreign_keys=[created_by])  # 수정: foreign_keys 명시
    
class PersonaPrompt(Base):
    __tablename__ = "persona_prompts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)
    llm_prompt = Column(Text, nullable=False)  # 이미 llm_prompt였음
    version = Column(Integer, nullable=False)  # 현재 활성 버전 번호 추가
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 관계 설정
    versions = relationship("PersonaPromptVersion", back_populates="prompt", cascade="all, delete-orphan")
    created_by_user = relationship("User", back_populates="persona_prompts")

    
class PersonaPromptVersion(Base):
    __tablename__ = "persona_prompt_versions"

    id = Column(Integer, primary_key=True, index=True)
    prompt_id = Column(Integer, ForeignKey("persona_prompts.id"), nullable=False)
    version = Column(Integer, nullable=False)
    llm_prompt = Column(Text, nullable=False)  # content에서 변경
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # 관계 설정
    prompt = relationship("PersonaPrompt", back_populates="versions")
    created_by_user = relationship("User", foreign_keys=[created_by])  # 수정: foreign_keys 명시
    
    
    
############################### persona 생성 관련 ###############################

class WorkflowPrompt(Base):
    __tablename__ = "workflow_prompts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)  # "컨셉 생성 프롬프트(캐릭터)" 등
    category = Column(String(50), nullable=False, index=True)  # concept, persona_info, summary, tags, image
    type = Column(String(10), nullable=True, index=True)  # CHAR, STORY, NULL
    llm_prompt = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)  # 현재 활성 버전 번호
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 관계 설정
    versions = relationship("WorkflowPromptVersion", back_populates="prompt", cascade="all, delete-orphan")
    created_by_user = relationship("User", back_populates="workflow_prompts")
    
    # 복합 인덱스 (category + type 조합으로 빠른 조회)
    __table_args__ = (
        Index('idx_workflow_category_type', 'category', 'type'),
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

# User 모델에 추가할 관계
# class User(Base):에 추가:
#     workflow_prompts = relationship("WorkflowPrompt", back_populates="created_by_user")
#     workflow_prompt_versions = relationship("WorkflowPromptVersion", back_populates="created_by_user")