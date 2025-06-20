"""
패스워드 해싱 유틸리티
순환 참조 문제 해결을 위해 분리
"""
from passlib.context import CryptContext

# 비밀번호 해싱 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """일반 비밀번호와 해시된 비밀번호를 비교합니다."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """일반 비밀번호를 해시 처리합니다."""
    return pwd_context.hash(password)