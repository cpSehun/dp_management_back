"""
애플리케이션 설정 관리
"""
import os
from typing import Optional
from pydantic import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # 기본 DB 설정
    mysql_user: str = os.getenv("MYSQL_USER", "dp_user")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "dp_password")
    mysql_host: str = os.getenv("MYSQL_HOST", "db")
    mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_database: str = os.getenv("MYSQL_DATABASE", "dp_management_db")
    
    # 외부 Persona DB 설정
    persona_db_user: str = os.getenv("PERSONA_DB_USER", "")
    persona_db_password: str = os.getenv("PERSONA_DB_PASSWORD", "")
    persona_db_host: str = os.getenv("PERSONA_DB_HOST", "43.203.24.147")
    persona_db_port: int = int(os.getenv("PERSONA_DB_PORT", "13306"))
    persona_db_database: str = os.getenv("PERSONA_DB_DATABASE", "daepa_agent")
    
    # 보안 설정
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key")
    algorithm: str = os.getenv("ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    session_secret_key: str = os.getenv("SESSION_SECRET_KEY", "your-session-secret")
    
    # Google OAuth 설정
    google_client_id: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")
    google_redirect_uri: Optional[str] = os.getenv("GOOGLE_REDIRECT_URI")
    
    # ComfyUI 설정
    comfyui_server: str = os.getenv("COMFYUI_SERVER", "http://192.168.0.151:8188")
    
    class Config:
        env_file = ".env"

# 전역 설정 객체
settings = Settings()