"""
보안 관련 함수들
도메인 기반 모듈화에 맞게 수정된 버전 - 순환 참조 해결
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import os
from jose import JWTError, jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel

# 패스워드 관련 함수는 별도 모듈에서 import (순환 참조 방지)
from app.core.password import verify_password, get_password_hash

# 기본 database import만 사용
from app import database

load_dotenv()

# JWT 설정
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# TokenData 클래스 정의
class TokenData(BaseModel):
    username: Optional[str] = None

# --- JWT 관련 함수 ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """JWT 액세스 토큰을 생성합니다."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str, credentials_exception):
    """JWT 토큰을 검증합니다."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    return token_data

# 현재 사용자 가져오기 (지연 import로 순환 참조 해결)
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    """현재 인증된 사용자를 가져옵니다."""
    # 지연 import로 순환 참조 해결
    from app.domains.users import crud
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user

# 활성 사용자만 허용
def get_current_active_user(current_user = Depends(get_current_user)):
    """현재 활성화된 사용자만 허용합니다."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# 관리자 사용자만 허용
def get_current_active_superuser(current_user = Depends(get_current_active_user)):
    """현재 활성화된 관리자 사용자만 허용합니다."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user