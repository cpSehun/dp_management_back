from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text # text 함수 임포트
from starlette.middleware.sessions import SessionMiddleware # SessionMiddleware 임포트
import os # os 임포트
from dotenv import load_dotenv # dotenv 임포트
import logging # logging 임포트 추가
from fastapi.middleware.cors import CORSMiddleware # CORS 임포트

logging.basicConfig(level=logging.INFO)

# database.py, models.py 등 다른 모듈 임포트 (추후 생성)
# 상대 경로 임포트를 절대 경로 임포트로 변경
import app.models as models # 상대 경로 임포트를 절대 경로 임포트로 변경
from app.database import engine, get_db # 상대 경로 임포트를 절대 경로 임포트로 변경

# .env 파일에서 환경 변수 로드
load_dotenv()

# SQLAlchemy 모델을 기반으로 데이터베이스 테이블 생성
# 애플리케이션 시작 시 테이블이 없으면 생성합니다.
# 프로덕션 환경에서는 Alembic과 같은 마이그레이션 도구 사용을 권장합니다.
models.Base.metadata.create_all(bind=engine)

# FastAPI 앱 인스턴스 생성
app = FastAPI(title="DP Management API", version="0.1.0")

# -------- CORS 미들웨어 추가 --------
origins = [
    "http://localhost:3000", # 프론트엔드 주소 
    # 필요하다면 다른 허용할 오리진 추가
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, # 자격 증명(쿠키, 인증 헤더 등) 허용 여부
    allow_methods=["*"], # 모든 HTTP 메소드 허용
    allow_headers=["*"], # 모든 HTTP 헤더 허용
)
# ----------------------------------

# SessionMiddleware 추가
# SECRET_KEY는 세션 데이터 암호화에 사용되므로, 강력하고 안전하게 관리해야 합니다.
# .env 파일에 SESSION_SECRET_KEY='your-strong-random-secret-key' 와 같이 설정합니다.
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

# 라우터 임포트 및 등록 (상대 경로를 절대 경로로 변경)
from app.routers import users # 상대 경로를 절대 경로로 변경
from app.routers import auth  # 상대 경로를 절대 경로로 변경
from app.routers import oauth_google # 상대 경로를 절대 경로로 변경
from app.routers import image_generator # 이미지 생성 라우터 추가

# API V1 경로 설정을 위한 부모 라우터 (선택 사항이지만 권장)
# from fastapi import APIRouter
# api_v1_router = APIRouter(prefix="/api/v1")
# api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])
# app.include_router(api_v1_router)

# 간단하게 직접 등록 (API 버전 관리가 덜 중요할 경우)
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(oauth_google.router, prefix="/api/v1/auth/google", tags=["OAuth - Google"])
app.include_router(image_generator.router, prefix="/api/v1/image-generator", tags=["Image Generator"])

# 루트 엔드포인트 (기본 테스트용)
@app.get("/")
async def read_root():
    """
    API 루트 경로. 간단한 환영 메시지를 반환합니다.
    """
    return {"message": "DP Management API에 오신 것을 환영합니다!"}

# 데이터베이스 연결 테스트 엔드포인트 (선택 사항)
@app.get("/db-test")
def test_db_connection(db: Session = Depends(get_db)):
    """
    데이터베이스 연결을 테스트하는 엔드포인트.
    간단한 쿼리를 실행하여 연결 상태를 확인합니다.
    """
    try:
        # 간단한 쿼리 실행 (text() 함수 사용)
        result = db.execute(text("SELECT 1"))
        result.fetchone() # 결과를 소비해야 할 수 있음
        return {"status": "success", "message": "데이터베이스 연결 성공"}
    except Exception as e:
        # 연결 실패 시 예외 발생
        raise HTTPException(status_code=500, detail=f"데이터베이스 연결 실패: {e}")

# 여기에 라우터 추가 (예: 사용자 관리, 프롬프트 관리 등)
# from .routers import users, prompts
# app.include_router(users.router)
# app.include_router(prompts.router)

# 참고: 실제 애플리케이션에서는 models.py, schemas.py, crud.py, routers/ 등을 구현해야 합니다.