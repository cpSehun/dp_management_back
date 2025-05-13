from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app import crud, models, schemas, database, security

router = APIRouter()

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

# 특정 사용자 조회 엔드포인트 (ID 기반)
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