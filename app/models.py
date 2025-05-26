from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float
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
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 관계 설정
    generated_images = relationship("GeneratedImage", back_populates="user")
    image_prompts = relationship("ImagePrompt", back_populates="created_by_user")
    persona_prompts = relationship("PersonaPrompt", back_populates="created_by_user")

class GeneratedImage(Base):
    """
    생성된 이미지 정보를 저장하는 SQLAlchemy 모델
    """
    __tablename__ = "generated_images"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    prompt = Column(Text, nullable=True)
    negative_prompt = Column(Text, nullable=True)
    model = Column(String(100), nullable=True)
    s3_url = Column(String(1024), nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    steps = Column(Integer, nullable=True)
    guidance = Column(Float, nullable=True)
    seed = Column(Integer, nullable=True)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 관계 설정
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