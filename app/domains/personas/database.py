"""
Persona 도메인 전용 데이터베이스 연결
외부 DB (43.203.24.147:13306 daepa_agent) 연결 관리
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# SQLAlchemy 연결 URL 생성
PERSONA_SQLALCHEMY_DATABASE_URL = (
    f"mysql+pymysql://{settings.persona_db_user}:{settings.persona_db_password}"
    f"@{settings.persona_db_host}:{settings.persona_db_port}/{settings.persona_db_schema}"
)

# SQLAlchemy 엔진 생성 (외부 DB용)
persona_engine = create_engine(
    PERSONA_SQLALCHEMY_DATABASE_URL,
    pool_recycle=1800,  # 1800초 (30분) 마다 커넥션 재활용
    pool_pre_ping=True,  # 연결 상태 확인
    echo=False  # SQL 쿼리 로깅 (개발 시에만 True)
)

# 데이터베이스 세션 생성기 (외부 DB용)
PersonaSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=persona_engine)

# SQLAlchemy 모델의 베이스 클래스 (외부 DB용)
PersonaBase = declarative_base()

# 의존성 주입을 위한 함수 (외부 DB용)
def get_persona_db():
    """
    외부 DB(t_persona 테이블) 연결을 위한 세션 생성 함수
    """
    db = PersonaSessionLocal()
    try:
        yield db
    finally:
        db.close()

# 연결 테스트 함수
def test_persona_db_connection():
    """
    외부 DB 연결 테스트
    """
    try:
        db = PersonaSessionLocal()
        # 간단한 테스트 쿼리
        result = db.execute(text("SELECT 1"))
        result.fetchone()
        db.close()
        logger.info("Persona DB connection successful")
        return True
    except Exception as e:
        logger.error(f"Persona DB connection failed: {e}")
        return False