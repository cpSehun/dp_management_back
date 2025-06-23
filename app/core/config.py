"""
애플리케이션 설정 관리
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings  # pydantic-settings 패키지에서 import
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # 기본 DB 설정
    mysql_user: str = "dp_user"
    mysql_password: str = "dp_password"
    mysql_host: str = "db"
    mysql_port: int = 3306
    mysql_database: str = "dp_management_db"
    
    # 외부 Persona DB 설정
    persona_db_user: str = ""
    persona_db_password: str = ""
    persona_db_host: str = "43.203.24.147"
    persona_db_port: int = 13306
    persona_db_database: str = "daepa_agent"
    
    # 보안 설정
    secret_key: str = "your-secret-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    session_secret_key: str = "your-session-secret"
    
    # Google OAuth 설정
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: Optional[str] = None
    
    # ComfyUI 설정
    comfyui_server: str = "http://192.168.0.151:8188"
    
    # 추가 환경 변수들 (에러 로그에서 확인된 것들)
    frontend_callback_url: Optional[str] = None
    next_public_api_base_url: Optional[str] = None
    
    # AWS 설정 (S3 관련)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "ap-northeast-2"
    s3_bucket_name: Optional[str] = None
    s3_folder: str = "generated-images"
    cloudfront_domain_name: Optional[str] = None
    
    # OpenAI 설정
    openai_api_key: Optional[str] = None
    
    # OpenRouter 설정
    open_router_api_key: Optional[str] = None
    
    # 텔레그램 설정
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    
    model_config = {
        "env_file": ".env",
        "extra": "ignore"  # 정의되지 않은 환경 변수 무시
    }

# 전역 설정 객체
settings = Settings()