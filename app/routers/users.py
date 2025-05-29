from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app import crud, models, schemas, database, security

router = APIRouter()

# 현재 사용자 정보 조회 엔드포인트 (반드시 /{user_id} 보다 먼저 위치해야 함)
@router.get("/me", response_model=schemas.User)
def read_current_user_info(current_user: models.User = Depends(security.get_current_active_user)):
    """현재 로그인한 사용자 정보 조회"""
    return current_user

# 사용자 생성 엔드포인트
@router.post("/", response_model=schemas.User)
def create_new_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    db_user_by_email = crud.get_user_by_email(db, email=user.email)
    if db_user_by_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    db_user_by_username = crud.get_user_by_username(db, username=user.username)
    if db_user_by_username:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)

# 사용자 목록 조회 엔드포인트 (인증 추가)
@router.get("/", response_model=List[schemas.User])
def read_users_list(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    users = crud.get_users(db, skip=skip, limit=limit)
    return users

# 사용자 활성화/비활성화 엔드포인트 (최고관리자 전용)
@router.put("/{user_id}/status", response_model=schemas.User)
def update_user_status(
    user_id: int,
    is_active: bool,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_active_superuser)  # 최고관리자만
):
    """사용자 활성화 상태 변경 (최고관리자 전용)"""
    updated_user = crud.update_user_status(db, user_id=user_id, is_active=is_active, updated_by_user_id=current_user.id)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user

# 사용자 권한 변경 엔드포인트 (최고관리자 전용)
@router.put("/{user_id}/role", response_model=schemas.User)
def update_user_role(
    user_id: int,
    is_superuser: bool, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_active_superuser)  # 최고관리자만
):
    """사용자 권한 변경 (최고관리자 전용)"""
    updated_user = crud.update_user_role(db, user_id=user_id, is_superuser=is_superuser)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user

# 특정 사용자 조회 엔드포인트 (ID 기반) - 반드시 맨 마지막에 위치
@router.get("/{user_id}", response_model=schemas.User)
def read_single_user(
    user_id: int, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user