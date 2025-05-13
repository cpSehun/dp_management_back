import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from fastapi import Request
import logging

# 로깅 설정
logger = logging.getLogger("uvicorn")

# .env 파일 로드 (Docker 환경에서는 docker-compose에서 환경 변수 주입)
load_dotenv()

# docker-compose.yml에서 설정한 환경 변수 또는 .env 파일에서 읽어옴 (기본값 설정)
MYSQL_USER = os.getenv("MYSQL_USER", "dp_user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "dp_password")
MYSQL_HOST = os.getenv("MYSQL_HOST", "db") # docker-compose 서비스 이름
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "dp_management_db")

# 포트 처리 (문자열 -> 정수 변환 시 오류 방지)
try:
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
except (TypeError, ValueError) as e:
    logger.warning(f"Invalid MYSQL_PORT value: {os.getenv('MYSQL_PORT')}. Using default port 3306.")
    MYSQL_PORT = 3306

# 설정 정보 로깅
logger.info(f"Database connection settings: Host={MYSQL_HOST}, Port={MYSQL_PORT}, DB={MYSQL_DATABASE}")

# SQLAlchemy 연결 URL 생성
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

# SQLAlchemy 엔진 생성
# connect_args는 MySQL 연결 시 타임존 관련 경고를 피하기 위해 추가 (선택 사항)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    # connect_args={"check_same_thread": False} # SQLite 사용 시 필요
)

# 데이터베이스 세션 생성기
# autocommit=False: 변경사항 자동 커밋 방지
# autoflush=False: 세션 내 객체 상태 자동 동기화 방지 (수동 관리)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# SQLAlchemy 모델의 베이스 클래스
Base = declarative_base()

# 의존성 주입(Dependency Injection)을 위한 함수
# FastAPI 엔드포인트 함수 내에서 이 함수를 호출하여 DB 세션을 얻음
def get_db():
    """
    FastAPI 의존성으로 사용될 데이터베이스 세션 생성 함수.
    요청마다 세션을 생성하고, 요청 처리가 끝나면 세션을 닫습니다.
    """
    db = SessionLocal()
    try:
        yield db # 세션 객체를 제너레이터로 반환
    finally:
        db.close() # 요청 완료 후 세션 닫기
