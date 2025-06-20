from app.domains.users import crud, schemas  # 도메인에서 import
from app import security, database  # 공통 모듈은 기존대로
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
import os
from dotenv import load_dotenv
from app.database import get_db
import logging


logger = logging.getLogger("uvicorn")

load_dotenv()

BACKEND_BASE_URL = os.getenv("NEXT_PUBLIC_API_BASE_URL")

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
    # 세션 클리어 (기존 상태 초기화)
    request.session.clear()
    
    redirect_uri = f"{BACKEND_BASE_URL}/api/v1/auth/google/callback"
    logger.info(f"Generated Redirect URI for Google (using BACKEND_BASE_URL): {redirect_uri}")
    
    # 새로운 상태로 OAuth 요청
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/callback", name="auth_google_callback")
async def auth_google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        # OAuth 토큰 획득 시 더 자세한 에러 처리
        token = await oauth.google.authorize_access_token(request)
        logger.info("Google OAuth 토큰 획득 성공")
    except Exception as e:
        logger.error(f"Google OAuth 토큰 획득 실패: {str(e)}")
        # 실패 시 세션 클리어 후 로그인 페이지로 리다이렉트
        request.session.clear()
        frontend_base_url = FRONTEND_CALLBACK_URL.rsplit('/', 3)[0] if FRONTEND_CALLBACK_URL else "http://localhost:3000"
        error_url = f"{frontend_base_url}/login?error=oauth_failed"
        return RedirectResponse(url=error_url)
    
    user_info = token.get('userinfo')
    if not user_info:
        logger.error("Google에서 사용자 정보를 가져올 수 없음")
        request.session.clear()
        frontend_base_url = FRONTEND_CALLBACK_URL.rsplit('/', 3)[0] if FRONTEND_CALLBACK_URL else "http://localhost:3000"
        error_url = f"{frontend_base_url}/login?error=no_userinfo"
        return RedirectResponse(url=error_url)

    google_email = user_info.get('email')
    google_name = user_info.get('name')

    if not google_email:
        logger.error("Google에서 이메일 정보를 제공하지 않음")
        request.session.clear()
        frontend_base_url = FRONTEND_CALLBACK_URL.rsplit('/', 3)[0] if FRONTEND_CALLBACK_URL else "http://localhost:3000"
        error_url = f"{frontend_base_url}/login?error=no_email"
        return RedirectResponse(url=error_url)

    logger.info(f"Google 로그인 시도: {google_email}")

    db_user = crud.get_user_by_email(db, email=google_email)
    if not db_user:
        # 새 사용자 생성
        username_candidate = google_email.split('@')[0]
        temp_username = username_candidate
        counter = 1
        while crud.get_user_by_username(db, username=temp_username):
            temp_username = f"{username_candidate}_{counter}"
            counter += 1
        
        user_in = schemas.UserCreate(
            username=temp_username,
            email=google_email,
            password=security.get_password_hash(os.urandom(16).hex()),
            full_name=google_name
        )
        db_user = crud.create_user(db, user=user_in)
        
        # 텔레그램으로 승인 요청 알림 전송
        from app.utils.telegram import send_user_approval_request
        try:
            send_user_approval_request(
                username=db_user.username,
                email=db_user.email,
                created_at=db_user.created_at
            )
        except Exception as e:
            logger.error(f"텔레그램 알림 전송 실패: {e}")
    
    # 세션 클리어 (OAuth 프로세스 완료)
    request.session.clear()
    
    # 사용자 활성화 상태 확인
    if not db_user.is_active:
        # 비활성 사용자는 특별한 토큰으로 콜백 핸들러를 통해 처리
        response_url = f"{FRONTEND_CALLBACK_URL}?token=approval_pending"
        logger.info(f"비활성 사용자 {db_user.username}을 승인 대기 페이지로 리다이렉트")
        return RedirectResponse(url=response_url)
    
    # 활성 사용자만 JWT 토큰 발급 및 dashboard로 리다이렉트
    app_access_token = security.create_access_token(data={"sub": db_user.username})
    response_url = f"{FRONTEND_CALLBACK_URL}?token={app_access_token}"
    logger.info(f"활성 사용자 {db_user.username}을 대시보드로 리다이렉트")
    return RedirectResponse(url=response_url)