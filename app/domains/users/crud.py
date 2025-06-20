"""
User 도메인 CRUD 함수들
기존 app/crud.py에서 User 관련 부분을 이동
"""
from sqlalchemy.orm import Session
from typing import List, Optional

from .models import User
from .schemas import UserCreate
from app.core.password import get_password_hash, verify_password  # 순환 참조 방지를 위해 core에서 import

def get_user(db: Session, user_id: int) -> Optional[User]:
    """ID로 사용자 조회"""
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """이메일로 사용자 조회"""
    return db.query(User).filter(User.email == email).first()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """사용자명으로 사용자 조회"""
    return db.query(User).filter(User.username == username).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    """사용자 목록 조회"""
    return db.query(User).offset(skip).limit(limit).all()

def create_user(db: Session, user: UserCreate) -> User:
    """새 사용자 생성"""
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """사용자 인증"""
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def update_user_status(db: Session, user_id: int, is_active: bool, updated_by_user_id: int) -> Optional[User]:
    """사용자 활성화 상태 변경"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        return None
    
    db_user.is_active = is_active
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_role(db: Session, user_id: int, is_superuser: bool) -> Optional[User]:
    """사용자 권한 변경"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        return None
    
    db_user.is_superuser = is_superuser
    db.commit()
    db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_id: int) -> Optional[User]:
    """사용자 삭제"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        return None
    
    db.delete(db_user)
    db.commit()
    return db_user