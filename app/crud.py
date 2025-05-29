from sqlalchemy.orm import Session, joinedload, selectinload
from app import models, schemas, security
from typing import List, Optional
from sqlalchemy import or_, desc
from sqlalchemy.sql import func

# 기존 사용자 관련 CRUD 함수들은 그대로 유지
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = security.get_password_hash(user.password)
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

def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username=username)
    if not user:
        return None
    if not security.verify_password(password, user.hashed_password):
        return None
    return user

# 사용자 활성화/비활성화 함수 추가
def update_user_status(db: Session, user_id: int, is_active: bool, updated_by_user_id: int) -> Optional[models.User]:
    """사용자 활성화 상태 변경"""
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        return None
    
    db_user.is_active = is_active
    db_user.updated_at = func.now()
    db.commit()
    db.refresh(db_user)
    
    # 활성화 시 텔레그램 알림 (선택적)
    if is_active:
        from app.utils.telegram import send_user_approval_notification
        try:
            send_user_approval_notification(db_user.username, db_user.email)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"사용자 승인 알림 전송 실패: {e}")
    
    return db_user

def update_user_role(db: Session, user_id: int, is_superuser: bool) -> Optional[models.User]:
    """사용자 권한 변경"""
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        return None
    
    db_user.is_superuser = is_superuser
    db_user.updated_at = func.now()
    db.commit()
    db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_id: int) -> Optional[models.User]:
    """
    사용자 삭제
    
    Args:
        db: 데이터베이스 세션
        user_id: 삭제할 사용자 ID
        
    Returns:
        Optional[models.User]: 삭제된 사용자 정보 또는 None
    """
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user:
        # 관련된 데이터들의 created_by를 NULL로 설정 (데이터 보존)
        
        # 생성된 이미지의 created_by를 NULL로 설정
        db.query(models.GeneratedImage).filter(
            models.GeneratedImage.created_by == user_id
        ).update({"created_by": None})
        
        # 이미지 프롬프트의 created_by를 NULL로 설정
        db.query(models.ImagePrompt).filter(
            models.ImagePrompt.created_by == user_id
        ).update({"created_by": None})
        
        # 이미지 프롬프트 버전의 created_by를 NULL로 설정
        db.query(models.ImagePromptVersion).filter(
            models.ImagePromptVersion.created_by == user_id
        ).update({"created_by": None})
        
        # 페르소나 프롬프트의 created_by를 NULL로 설정
        db.query(models.PersonaPrompt).filter(
            models.PersonaPrompt.created_by == user_id
        ).update({"created_by": None})
        
        # 페르소나 프롬프트 버전의 created_by를 NULL로 설정
        db.query(models.PersonaPromptVersion).filter(
            models.PersonaPromptVersion.created_by == user_id
        ).update({"created_by": None})
        
        # 사용자 삭제
        db.delete(db_user)
        db.commit()
        return db_user
    return None

# --- GeneratedImage CRUD (기존 코드 유지) ---

def get_generated_image(db: Session, image_id: int) -> Optional[models.GeneratedImage]:
    """생성된 이미지 단건 조회 - 사용자 정보 포함"""
    return db.query(models.GeneratedImage).options(
        joinedload(models.GeneratedImage.user)
    ).filter(models.GeneratedImage.id == image_id).first()

def get_generated_images(db: Session, skip: int = 0, limit: int = 100, search_term: Optional[str] = None) -> List[models.GeneratedImage]:
    """생성된 이미지 목록 조회 - 사용자 정보 포함"""
    query = db.query(models.GeneratedImage).options(
        joinedload(models.GeneratedImage.user)
    )
    
    if search_term:
        search_filter = f"%{search_term}%"
        query = query.filter(
            or_(
                models.GeneratedImage.name.ilike(search_filter),
                models.GeneratedImage.prompt.ilike(search_filter),
                models.GeneratedImage.model.ilike(search_filter),
                models.GeneratedImage.tags.ilike(search_filter)
            )
        )
    
    return query.order_by(desc(models.GeneratedImage.created_at)).offset(skip).limit(limit).all()

def get_generated_images_count(db: Session, search_term: Optional[str] = None) -> int:
    """생성된 이미지 총 개수"""
    query = db.query(models.GeneratedImage)
    
    if search_term:
        search_filter = f"%{search_term}%"
        query = query.filter(
            or_(
                models.GeneratedImage.name.ilike(search_filter),
                models.GeneratedImage.prompt.ilike(search_filter),
                models.GeneratedImage.model.ilike(search_filter),
                models.GeneratedImage.tags.ilike(search_filter)
            )
        )
    
    return query.count()

def create_generated_image(db: Session, image_in: schemas.GeneratedImageCreate, user_id: Optional[int] = None) -> models.GeneratedImage:
    """새 생성 이미지 저장"""
    db_image = models.GeneratedImage(
        name=image_in.name,
        prompt=image_in.prompt,
        model=image_in.model,
        s3_url=image_in.s3_url,
        tags=image_in.tags,
        steps=image_in.steps if image_in.model == "flux-dev" else None,
        seed=image_in.seed if image_in.model == "flux-dev" else None,
        created_by=user_id,
    )
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    return db_image

def delete_generated_image(db: Session, image_id: int) -> Optional[models.GeneratedImage]:
    """생성된 이미지 삭제"""
    db_image = db.query(models.GeneratedImage).filter(models.GeneratedImage.id == image_id).first()
    if db_image:
        db.delete(db_image)
        db.commit()
        return db_image
    return None

# --- ImagePrompt CRUD (기존 코드 유지) ---

def get_image_prompt(db: Session, prompt_id: int) -> Optional[models.ImagePrompt]:
    """현재 활성 프롬프트 조회 - 사용자 정보 포함"""
    from sqlalchemy.orm import selectinload
    return db.query(models.ImagePrompt).options(
        joinedload(models.ImagePrompt.created_by_user),
        selectinload(models.ImagePrompt.versions).joinedload(models.ImagePromptVersion.created_by_user)
    ).filter(models.ImagePrompt.id == prompt_id).first()

def get_image_prompts(db: Session, skip: int = 0, limit: int = 100, search_term: Optional[str] = None) -> List[models.ImagePrompt]:
    """현재 활성 프롬프트 목록 조회 (prompts 테이블에서)"""
    from sqlalchemy.orm import selectinload
    query = db.query(models.ImagePrompt).options(
        joinedload(models.ImagePrompt.created_by_user),
        selectinload(models.ImagePrompt.versions).joinedload(models.ImagePromptVersion.created_by_user)
    )
    if search_term:
        search_filter = f"%{search_term}%"
        query = query.filter(
            or_(
                models.ImagePrompt.name.ilike(search_filter),
                models.ImagePrompt.llm_prompt.ilike(search_filter)
            )
        )
    return query.order_by(desc(models.ImagePrompt.updated_at)).offset(skip).limit(limit).all()

def get_image_prompts_count(db: Session, search_term: Optional[str] = None) -> int:
    """현재 활성 프롬프트 총 개수"""
    query = db.query(models.ImagePrompt)
    if search_term:
        search_filter = f"%{search_term}%"
        query = query.filter(
            or_(
                models.ImagePrompt.name.ilike(search_filter),
                models.ImagePrompt.llm_prompt.ilike(search_filter)
            )
        )
    return query.count()

def create_image_prompt(db: Session, prompt_in: schemas.ImagePromptCreate, user_id: Optional[int] = None) -> models.ImagePrompt:
    """새 프롬프트 생성 (v1으로 시작)"""
    # 1. prompts 테이블에 저장 (version=1)
    db_prompt = models.ImagePrompt(
        name=prompt_in.name,
        llm_prompt=prompt_in.llm_prompt,
        version=1,
        created_by=user_id,
    )
    db.add(db_prompt)
    db.flush()

    # 2. prompt_versions 테이블에도 저장 (version=1)
    db_version = models.ImagePromptVersion(
        prompt_id=db_prompt.id,
        version=1,
        llm_prompt=prompt_in.llm_prompt,
        created_by=user_id,
    )
    db.add(db_version)
    
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

def update_image_prompt(db: Session, prompt_id: int, prompt_in: schemas.ImagePromptUpdate, user_id: Optional[int] = None) -> Optional[models.ImagePrompt]:
    """프롬프트 수정 (새 버전 생성)"""
    db_prompt = db.query(models.ImagePrompt).filter(models.ImagePrompt.id == prompt_id).first()
    if not db_prompt:
        return None

    # 1. 현재 prompts 테이블 내용을 prompt_versions에 백업 (이미 있다면 스킵)
    existing_version = db.query(models.ImagePromptVersion).filter(
        models.ImagePromptVersion.prompt_id == prompt_id,
        models.ImagePromptVersion.version == db_prompt.version,
        models.ImagePromptVersion.llm_prompt == db_prompt.llm_prompt
    ).first()
    
    if not existing_version:
        backup_version = models.ImagePromptVersion(
            prompt_id=db_prompt.id,
            version=db_prompt.version,
            llm_prompt=db_prompt.llm_prompt,
            created_by=db_prompt.created_by,
            created_at=db_prompt.updated_at or db_prompt.created_at
        )
        db.add(backup_version)

    # 2. 모든 버전 중 가장 높은 버전 번호 찾기
    max_version = db.query(func.max(models.ImagePromptVersion.version)).filter(
        models.ImagePromptVersion.prompt_id == prompt_id
    ).scalar() or 0
    
    next_version = max(max_version, db_prompt.version) + 1

    # 3. prompts 테이블 업데이트
    update_data = prompt_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_prompt, field, value)
    
    db_prompt.version = next_version
    db_prompt.updated_at = func.now()

    # 4. 새 버전을 prompt_versions에 저장
    new_version = models.ImagePromptVersion(
        prompt_id=db_prompt.id,
        version=next_version,
        llm_prompt=db_prompt.llm_prompt,
        created_by=user_id,
    )
    db.add(new_version)

    db.commit()
    db.refresh(db_prompt)
    return db_prompt

def rollback_image_prompt(db: Session, prompt_id: int, target_version: int, user_id: Optional[int] = None) -> Optional[models.ImagePrompt]:
    """프롬프트 롤백 (지정된 버전으로 복원)"""
    db_prompt = db.query(models.ImagePrompt).filter(models.ImagePrompt.id == prompt_id).first()
    if not db_prompt:
        return None

    # 1. 타겟 버전 찾기
    target_version_data = db.query(models.ImagePromptVersion).filter(
        models.ImagePromptVersion.prompt_id == prompt_id,
        models.ImagePromptVersion.version == target_version
    ).first()
    
    if not target_version_data:
        return None

    # 2. 현재 prompts 내용을 versions에 백업
    existing_version = db.query(models.ImagePromptVersion).filter(
        models.ImagePromptVersion.prompt_id == prompt_id,
        models.ImagePromptVersion.version == db_prompt.version,
        models.ImagePromptVersion.llm_prompt == db_prompt.llm_prompt
    ).first()
    
    if not existing_version:
        backup_version = models.ImagePromptVersion(
            prompt_id=db_prompt.id,
            version=db_prompt.version,
            llm_prompt=db_prompt.llm_prompt,
            created_by=db_prompt.created_by,
            created_at=db_prompt.updated_at or db_prompt.created_at
        )
        db.add(backup_version)

    # 3. prompts 테이블을 타겟 버전으로 복원
    db_prompt.llm_prompt = target_version_data.llm_prompt
    db_prompt.version = target_version
    db_prompt.updated_at = func.now()

    db.commit()
    db.refresh(db_prompt)
    return db_prompt

# --- PersonaPrompt CRUD (기존 코드 유지) ---

def get_persona_prompt(db: Session, prompt_id: int) -> Optional[models.PersonaPrompt]:
    from sqlalchemy.orm import selectinload
    return db.query(models.PersonaPrompt).options(
        joinedload(models.PersonaPrompt.created_by_user),
        selectinload(models.PersonaPrompt.versions).joinedload(models.PersonaPromptVersion.created_by_user)
    ).filter(models.PersonaPrompt.id == prompt_id).first()

def get_persona_prompts(db: Session, skip: int = 0, limit: int = 100, search_term: Optional[str] = None) -> List[models.PersonaPrompt]:
    """현재 활성 프롬프트 목록 조회 - 사용자 정보 포함"""
    from sqlalchemy.orm import selectinload
    query = db.query(models.PersonaPrompt).options(
        joinedload(models.PersonaPrompt.created_by_user),
        selectinload(models.PersonaPrompt.versions).joinedload(models.PersonaPromptVersion.created_by_user)
    )
    if search_term:
        search_filter = f"%{search_term}%"
        query = query.filter(
            or_(
                models.PersonaPrompt.name.ilike(search_filter),
                models.PersonaPrompt.llm_prompt.ilike(search_filter)
            )
        )
    return query.order_by(desc(models.PersonaPrompt.updated_at)).offset(skip).limit(limit).all()

def get_persona_prompts_count(db: Session, search_term: Optional[str] = None) -> int:
    """현재 활성 프롬프트 총 개수"""
    query = db.query(models.PersonaPrompt)
    if search_term:
        search_filter = f"%{search_term}%"
        query = query.filter(
            or_(
                models.PersonaPrompt.name.ilike(search_filter),
                models.PersonaPrompt.llm_prompt.ilike(search_filter)
            )
        )
    return query.count()

def create_persona_prompt(db: Session, prompt_in: schemas.PersonaPromptCreate, user_id: Optional[int] = None) -> models.PersonaPrompt:
    db_prompt = models.PersonaPrompt(
        name=prompt_in.name,
        llm_prompt=prompt_in.llm_prompt,
        version=1,
        created_by=user_id,
    )
    db.add(db_prompt)
    db.flush()

    db_version = models.PersonaPromptVersion(
        prompt_id=db_prompt.id,
        version=1,
        llm_prompt=prompt_in.llm_prompt,
        created_by=user_id,
    )
    db.add(db_version)
    
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

def update_persona_prompt(db: Session, prompt_id: int, prompt_in: schemas.PersonaPromptUpdate, user_id: Optional[int] = None) -> Optional[models.PersonaPrompt]:
    db_prompt = db.query(models.PersonaPrompt).filter(models.PersonaPrompt.id == prompt_id).first()
    if not db_prompt:
        return None

    existing_version = db.query(models.PersonaPromptVersion).filter(
        models.PersonaPromptVersion.prompt_id == prompt_id,
        models.PersonaPromptVersion.version == db_prompt.version,
        models.PersonaPromptVersion.llm_prompt == db_prompt.llm_prompt
    ).first()
    
    if not existing_version:
        backup_version = models.PersonaPromptVersion(
            prompt_id=db_prompt.id,
            version=db_prompt.version,
            llm_prompt=db_prompt.llm_prompt,
            created_by=db_prompt.created_by,
            created_at=db_prompt.updated_at or db_prompt.created_at
        )
        db.add(backup_version)

    # 모든 버전 중 가장 높은 버전 번호 찾기
    max_version = db.query(func.max(models.PersonaPromptVersion.version)).filter(
        models.PersonaPromptVersion.prompt_id == prompt_id
    ).scalar() or 0
    
    next_version = max(max_version, db_prompt.version) + 1
    
    # prompts 테이블 업데이트
    update_data = prompt_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_prompt, field, value)
    
    db_prompt.version = next_version
    db_prompt.updated_at = func.now()

    # 새 버전을 prompt_versions에 저장
    new_version = models.PersonaPromptVersion(
        prompt_id=db_prompt.id,
        version=next_version,
        llm_prompt=db_prompt.llm_prompt,
        created_by=user_id,
    )
    db.add(new_version)

    db.commit()
    db.refresh(db_prompt)
    return db_prompt

def rollback_persona_prompt(db: Session, prompt_id: int, target_version: int, user_id: Optional[int] = None) -> Optional[models.PersonaPrompt]:
    db_prompt = db.query(models.PersonaPrompt).filter(models.PersonaPrompt.id == prompt_id).first()
    if not db_prompt:
        return None

    target_version_data = db.query(models.PersonaPromptVersion).filter(
        models.PersonaPromptVersion.prompt_id == prompt_id,
        models.PersonaPromptVersion.version == target_version
    ).first()
    
    if not target_version_data:
        return None

    existing_version = db.query(models.PersonaPromptVersion).filter(
        models.PersonaPromptVersion.prompt_id == prompt_id,
        models.PersonaPromptVersion.version == db_prompt.version,
        models.PersonaPromptVersion.llm_prompt == db_prompt.llm_prompt
    ).first()
    
    if not existing_version:
        backup_version = models.PersonaPromptVersion(
            prompt_id=db_prompt.id,
            version=db_prompt.version,
            llm_prompt=db_prompt.llm_prompt,
            created_by=db_prompt.created_by,
            created_at=db_prompt.updated_at or db_prompt.created_at
        )
        db.add(backup_version)

    db_prompt.llm_prompt = target_version_data.llm_prompt
    db_prompt.version = target_version
    db_prompt.updated_at = func.now()

    db.commit()
    db.refresh(db_prompt)
    return db_prompt