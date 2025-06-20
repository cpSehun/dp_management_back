"""
공통 예외 클래스들
"""
from fastapi import HTTPException
from typing import Optional

class DomainException(Exception):
    """도메인 기본 예외"""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class NotFoundError(DomainException):
    """리소스를 찾을 수 없음"""
    def __init__(self, resource: str, identifier: str):
        message = f"{resource}을(를) 찾을 수 없습니다: {identifier}"
        super().__init__(message, 404)

class ValidationError(DomainException):
    """데이터 검증 오류"""
    def __init__(self, message: str):
        super().__init__(message, 400)

class DatabaseConnectionError(DomainException):
    """데이터베이스 연결 오류"""
    def __init__(self, database: str):
        message = f"{database} 데이터베이스 연결에 실패했습니다."
        super().__init__(message, 503)