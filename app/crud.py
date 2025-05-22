from sqlalchemy.orm import Session
from app import models, schemas, security # security 모듈 임포트
import json # tags를 JSON 문자열로 저장/로드 할 경우
from typing import List, Optional, Union # Union은 여기서는 사용되지 않음
from sqlalchemy import or_ # or_ 조건 추가
from sqlalchemy.sql import func

# 사용자 ID로 사용자 조회
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

# 이메일로 사용자 조회
def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

# 사용자 이름으로 사용자 조회
def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

# 여러 사용자 조회 (페이징 처리)
def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

# 사용자 생성
def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = security.get_password_hash(user.password) # 비밀번호 해싱
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# 사용자 인증 (로그인)
def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username=username)
    if not user:
        return None
    if not security.verify_password(password, user.hashed_password):
        return None
    return user

# --- ImagePrompt CRUD ---

def get_image_prompt(db: Session, prompt_id: int) -> Optional[models.ImagePrompt]:
    return db.query(models.ImagePrompt).filter(models.ImagePrompt.id == prompt_id).first()

def get_image_prompts(db: Session, skip: int = 0, limit: int = 100, search_term: Optional[str] = None) -> List[models.ImagePrompt]:
    query = db.query(models.ImagePrompt)
    if search_term:
        search_filter = f"%{search_term}%"
        # 검색 조건: 이름, 설명, 태그 (내용은 PromptVersion에 있으므로 별도 처리 또는 조인 필요)
        # 여기서는 ImagePrompt의 필드만 검색한다고 가정
        # PromptVersion의 content까지 검색하려면 join 및 추가 조건 필요
        query = query.filter(
            or_(
                models.ImagePrompt.name.ilike(search_filter),
                models.ImagePrompt.description.ilike(search_filter),
                models.ImagePrompt.tags.ilike(search_filter) 
            )
        )
    return query.order_by(models.ImagePrompt.updated_at.desc()).offset(skip).limit(limit).all()

def get_image_prompts_count(db: Session, search_term: Optional[str] = None) -> int:
    query = db.query(models.ImagePrompt)
    if search_term:
        search_filter = f"%{search_term}%"
        query = query.filter(
            or_(
                models.ImagePrompt.name.ilike(search_filter),
                models.ImagePrompt.description.ilike(search_filter),
                models.ImagePrompt.tags.ilike(search_filter)
            )
        )
    return query.count()

def create_image_prompt(db: Session, prompt_in: schemas.ImagePromptCreate) -> models.ImagePrompt:
    # Tags 처리: 리스트를 문자열로 변환 (구현 방식에 따라 다를 수 있음)
    tags_str = ",".join(prompt_in.tags) if prompt_in.tags else None

    db_prompt = models.ImagePrompt(
        name=prompt_in.name,
        description=prompt_in.description,
        tags=tags_str,
        # is_enabled=prompt_in.is_enabled, # is_enabled 제거
    )
    db.add(db_prompt)
    db.flush() # db_prompt의 id를 얻기 위해 flush

    for version_data in prompt_in.versions:
        db_version = models.ImagePromptVersion(
            prompt_id=db_prompt.id,
            content=version_data.content,
            is_active=version_data.is_active,
            # version_number는 자동 증가 또는 다른 로직으로 설정될 수 있음 (모델 정의에 따라 다름)
        )
        db.add(db_version)

    db.commit()
    db.refresh(db_prompt)
    return db_prompt

def update_image_prompt(db: Session, prompt_id: int, prompt_in: schemas.ImagePromptUpdate) -> Optional[models.ImagePrompt]:
    db_prompt = db.query(models.ImagePrompt).filter(models.ImagePrompt.id == prompt_id).first()
    if not db_prompt:
        return None

    update_data = prompt_in.model_dump(exclude_unset=True)
    
    if "tags" in update_data and update_data["tags"] is not None:
        update_data["tags"] = ",".join(update_data["tags"])
    elif "tags" in update_data and update_data["tags"] is None:
        update_data["tags"] = None # 명시적으로 None으로 설정
    # else: # tags가 요청에 없으면 기존 값 유지 (model_dump(exclude_unset=True) 덕분)
        # pass

    # is_enabled 필드는 prompt_in에 더 이상 없으므로 관련 로직 제거
    # if "is_enabled" in update_data:
    #     db_prompt.is_enabled = update_data["is_enabled"]

    for field, value in update_data.items():
        if field != "tags": # tags는 위에서 처리
            setattr(db_prompt, field, value)
    
    db_prompt.updated_at = func.now() # updated_at 명시적 업데이트
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

def delete_image_prompt(db: Session, prompt_id: int) -> Optional[models.ImagePrompt]:
    db_prompt = get_image_prompt(db, prompt_id)
    if not db_prompt:
        return None
    db.delete(db_prompt)
    db.commit()
    return db_prompt

# --- PromptVersion CRUD (선택적) ---

def create_image_prompt_version(db: Session, prompt_id: int, version_data: schemas.ImagePromptVersionCreate) -> models.ImagePromptVersion:
    if version_data.is_active:
        db.query(models.ImagePromptVersion).filter(models.ImagePromptVersion.prompt_id == prompt_id)\
            .update({"is_active": False})

    db_version = models.ImagePromptVersion(
        prompt_id=prompt_id,
        content=version_data.content,
        is_active=version_data.is_active
    )
    db.add(db_version)
    db.commit()
    db.refresh(db_version)
    return db_version

def set_active_image_version(db: Session, prompt_id: int, version_id: int) -> Optional[models.ImagePrompt]:
    db_prompt = get_image_prompt(db, prompt_id)
    if not db_prompt:
        return None
        
    found_version = False
    for version in db_prompt.versions:
        if version.id == version_id:
            version.is_active = True
            found_version = True
        else:
            version.is_active = False
            
    if not found_version:
        return None

    db.commit()
    db.refresh(db_prompt)
    return db_prompt

# --- PersonaPrompt CRUD (Similar to ImagePrompt) ---

def get_persona_prompt(db: Session, prompt_id: int) -> Optional[models.PersonaPrompt]: # Model name changed
    return db.query(models.PersonaPrompt).filter(models.PersonaPrompt.id == prompt_id).first()

def get_persona_prompts(db: Session, skip: int = 0, limit: int = 100, search_term: Optional[str] = None) -> List[models.PersonaPrompt]: # Model name changed
    query = db.query(models.PersonaPrompt)
    if search_term:
        search_filter = f"%{search_term}%"
        query = query.filter(
            or_(
                models.PersonaPrompt.name.ilike(search_filter),
                models.PersonaPrompt.description.ilike(search_filter),
                models.PersonaPrompt.tags.ilike(search_filter) 
            )
        )
    return query.order_by(models.PersonaPrompt.updated_at.desc()).offset(skip).limit(limit).all()

def get_persona_prompts_count(db: Session, search_term: Optional[str] = None) -> int: # Model name changed
    query = db.query(models.PersonaPrompt)
    if search_term:
        search_filter = f"%{search_term}%"
        query = query.filter(
            or_(
                models.PersonaPrompt.name.ilike(search_filter),
                models.PersonaPrompt.description.ilike(search_filter),
                models.PersonaPrompt.tags.ilike(search_filter)
            )
        )
    return query.count()

def create_persona_prompt(db: Session, prompt_in: schemas.PersonaPromptCreate) -> models.PersonaPrompt:
    tags_str = ",".join(prompt_in.tags) if prompt_in.tags else None
    db_prompt = models.PersonaPrompt(
        name=prompt_in.name,
        description=prompt_in.description,
        tags=tags_str,
        # is_enabled=prompt_in.is_enabled, # is_enabled 제거
    )
    db.add(db_prompt)
    db.flush()

    for version_data in prompt_in.versions:
        db_version = models.PersonaPromptVersion(
            prompt_id=db_prompt.id,
            content=version_data.content,
            is_active=version_data.is_active,
        )
        db.add(db_version)
    
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

def update_persona_prompt(db: Session, prompt_id: int, prompt_in: schemas.PersonaPromptUpdate) -> Optional[models.PersonaPrompt]:
    db_prompt = db.query(models.PersonaPrompt).filter(models.PersonaPrompt.id == prompt_id).first()
    if not db_prompt:
        return None

    update_data = prompt_in.model_dump(exclude_unset=True)

    if "tags" in update_data and update_data["tags"] is not None:
        update_data["tags"] = ",".join(update_data["tags"])
    elif "tags" in update_data and update_data["tags"] is None:
        update_data["tags"] = None

    # is_enabled 필드 관련 로직 제거

    for field, value in update_data.items():
        if field != "tags":
            setattr(db_prompt, field, value)
            
    db_prompt.updated_at = func.now()
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

def delete_persona_prompt(db: Session, prompt_id: int) -> Optional[models.PersonaPrompt]: # Model name changed
    db_prompt = get_persona_prompt(db, prompt_id)
    if not db_prompt:
        return None
    db.delete(db_prompt)
    db.commit()
    return db_prompt


def create_persona_prompt_version(db: Session, prompt_id: int, version_data: schemas.PersonaPromptVersionCreate) -> models.PersonaPromptVersion: # Schema and Model names changed
    # Assuming PersonaPromptVersion model and PersonaPromptVersionCreate schema exist
    if version_data.is_active:
        # Deactivate other versions for this persona prompt
        db.query(models.PersonaPromptVersion).filter(models.PersonaPromptVersion.prompt_id == prompt_id)\
            .update({"is_active": False})

    db_version = models.PersonaPromptVersion(
        prompt_id=prompt_id,
        content=version_data.content,
        is_active=version_data.is_active
    )
    db.add(db_version)
    db.commit()
    db.refresh(db_version)
    return db_version

def set_active_persona_version(db: Session, prompt_id: int, version_id: int) -> Optional[models.PersonaPrompt]: # Model names changed
    db_prompt = get_persona_prompt(db, prompt_id)
    if not db_prompt:
        return None
        
    found_version = False
    # Assuming versions are related to PersonaPrompt model as 'versions'
    for version in db_prompt.versions: 
        if version.id == version_id:
            version.is_active = True
            found_version = True
        else:
            version.is_active = False
            
    if not found_version:
        return None # Or raise HTTPException

    db.commit()
    db.refresh(db_prompt)
    return db_prompt

# 기존 CRUD 함수들 아래에 추가합니다. 