"""
메인 애플리케이션 - 도메인 기반 모듈화 적용
"""
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware
import logging
from fastapi.middleware.cors import CORSMiddleware

# 기존 모듈들 (공통 사용)
from app.database import engine, get_db
from app.security import get_current_active_user

# 도메인별 모듈 임포트
from app.domains import (
    users_router,
    personas_router,
    # images_router,    # 아직 마이그레이션 전
    # prompts_router    # 아직 마이그레이션 전
)

# 기존 라우터들 (아직 마이그레이션 안된 것들)
from app.routers import auth, oauth_google, image_generator, generated_images, llm, workflow_prompts

# 설정
from app.core.config import settings

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 모든 도메인의 모델들을 Base에 등록 (마이그레이션 후 정리)
from app.domains.users.models import User  # User 모델 임포트
import app.models as legacy_models  # 기존 모델들 (임시)

# 데이터베이스 테이블 생성
legacy_models.Base.metadata.create_all(bind=engine)

# FastAPI 앱 생성
app = FastAPI(
    title="DP Management API",
    description="도메인 기반 모듈화를 적용한 DP 관리 시스템 API",
    version="2.0.0",
)

# CORS 미들웨어
origins = [
    "http://localhost:3000",
    "http://192.168.0.105:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 세션 미들웨어
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)

# 도메인별 라우터 등록
app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])
app.include_router(personas_router, prefix="/api/v1/persona", tags=["Persona"])

# 기존 라우터들 (아직 마이그레이션 안된 것들)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(oauth_google.router, prefix="/api/v1/auth/google", tags=["OAuth - Google"])
app.include_router(image_generator.router, prefix="/api/v1/image-generator", tags=["Image Generator"])
app.include_router(generated_images.router, tags=["Generated Images"])
app.include_router(llm.router, tags=["LLM"])
app.include_router(workflow_prompts.router, prefix="/api/v1/prompts/workflow", tags=["Workflow Prompts"])

# 시작 이벤트
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 실행되는 이벤트"""
    from app.domains.personas.database import test_persona_db_connection
    
    # 외부 DB 연결 테스트
    if test_persona_db_connection():
        logger.info("✅ 외부 Persona DB 연결 성공")
    else:
        logger.warning("⚠️ 외부 Persona DB 연결 실패 - 기능이 제한될 수 있습니다")

# 루트 엔드포인트
@app.get("/")
async def read_root():
    """API 루트 경로"""
    return {
        "message": "DP Management API에 오신 것을 환영합니다!",
        "version": "2.0.0",
        "domains": ["users", "personas"]
    }

# 헬스체크 엔드포인트
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """애플리케이션 상태 확인"""
    try:
        # 기본 DB 연결 테스트
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")