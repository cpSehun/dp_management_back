from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
import os
from dotenv import load_dotenv

from app import crud, schemas, security, database
from app.database import get_db

import logging
logger = logging.getLogger("uvicorn") # 로거 추가

load_dotenv()

BACKEND_BASE_URL = os.getenv("NEXT_PUBLIC_API_BASE_URL") # 기본값 설정

router = APIRouter()

CONF_URL = 'https://accounts.google.com/.well-known/openid-configuration'
oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url=CONF_URL,
    client_kwargs={
        'scope': 'openid email profile'
    }
)

FRONTEND_CALLBACK_URL = os.getenv("FRONTEND_CALLBACK_URL")

@router.get("/login")
async def login_via_google(request: Request):
    # request.url_for 대신 명시적으로 URI 구성
    # 백엔드 자신의 콜백 엔드포인트 경로를 조합
    redirect_uri = f"{BACKEND_BASE_URL}/api/v1/auth/google/callback"
    logger.info(f"Generated Redirect URI for Google (using BACKEND_BASE_URL): {redirect_uri}") # 로그 수정
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/callback", name="auth_google_callback")
async def auth_google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Could not validate credentials: {e}")
    
    user_info = token.get('userinfo')
    if not user_info:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not fetch user info from Google")

    google_email = user_info.get('email')
    google_name = user_info.get('name')
    # google_picture = user_info.get('picture') # 프로필 사진도 가져올 수 있음

    if not google_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email not provided by Google")

    db_user = crud.get_user_by_email(db, email=google_email)
    if not db_user:
        # 새 사용자 생성
        # username은 email 앞부분 또는 다른 방식으로 생성 가능
        username_candidate = google_email.split('@')[0]
        # 이미 존재하는 username일 경우 대비하여 고유하게 만듦 (예: _1, _2 추가)
        temp_username = username_candidate
        counter = 1
        while crud.get_user_by_username(db, username=temp_username):
            temp_username = f"{username_candidate}_{counter}"
            counter += 1
        
        # OAuth 사용자는 비밀번호가 없으므로, 임의의 값 또는 빈 값으로 처리
        # 또는 User 모델에 provider 필드 추가하여 구분
        user_in = schemas.UserCreate(
            username=temp_username,
            email=google_email,
            password=security.get_password_hash(os.urandom(16).hex()), # 임의의 비번, 실제 사용 안함
            full_name=google_name
        )
        db_user = crud.create_user(db, user=user_in)
    
    # 우리 앱의 JWT 생성
    # db_user.username 이 아닌, 실제 User 모델에 있는 username 사용
    app_access_token = security.create_access_token(data={"sub": db_user.username})
    
    # 프론트엔드로 JWT와 함께 리다이렉트
    # 예: http://localhost:3000/auth/google/callback-receiver?token=OUR_APP_JWT
    response_url = f"{FRONTEND_CALLBACK_URL}?token={app_access_token}"
    return RedirectResponse(url=response_url) 