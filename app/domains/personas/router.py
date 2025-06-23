"""
Persona 도메인 라우터
기존 app/routers/persona.py 내용을 도메인 구조에 맞게 이동
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from .database import get_persona_db, test_persona_db_connection
from .schemas import Persona, PersonaCreate, PersonaUpdate, PersonaListResponse
from . import crud
from app.security import get_current_active_user

logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter()

@router.get("/", response_model=List[Persona])
async def get_persona_list(
    skip: int = Query(0, ge=0, description="건너뛸 레코드 수"),
    limit: int = Query(20, ge=1, le=100, description="가져올 레코드 수"),
    search: Optional[str] = Query(None, description="검색어 (이름, ID, 타입, 상태 등)"),
    db: Session = Depends(get_persona_db),
    current_user = Depends(get_current_active_user)
):
    """페르소나 목록 조회"""
    try:
        # 데이터베이스 연결 테스트
        if not crud.test_db_connection(db):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="외부 데이터베이스 연결에 실패했습니다."
            )
        
        # 페르소나 목록 조회
        personas = crud.get_personas(db, skip=skip, limit=limit, search=search)
        
        logger.info(f"Retrieved {len(personas)} personas for user {current_user.username}")
        return personas
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_persona_list: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="페르소나 목록을 가져오는 중 오류가 발생했습니다."
        )

@router.get("/paginated", response_model=PersonaListResponse)
async def get_persona_paginated(
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 항목 수"),
    search: Optional[str] = Query(None, description="검색어"),
    db: Session = Depends(get_persona_db),
    current_user = Depends(get_current_active_user)
):
    """
    페이지네이션이 적용된 페르소나 목록 조회
    """
    try:
        # 데이터베이스 연결 테스트
        if not test_persona_db_connection():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="외부 데이터베이스 연결에 실패했습니다."
            )
        
        # skip 계산
        skip = (page - 1) * limit
        
        # 총 개수 및 목록 조회
        total_items = crud.get_personas_count(db, search=search)
        personas = crud.get_personas(db, skip=skip, limit=limit, search=search)
        
        response = PersonaListResponse(
            total_items=total_items,
            items=personas,
            page=page,
            limit=limit
        )
        
        logger.info(f"Retrieved paginated personas: page={page}, total={total_items}, returned={len(personas)}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_persona_paginated: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="페르소나 목록을 가져오는 중 오류가 발생했습니다."
        )

@router.get("/test/connection")
async def test_persona_db_connection_endpoint(
    db: Session = Depends(get_persona_db),
    current_user = Depends(get_current_active_user)
):
    """
    외부 데이터베이스 연결 테스트
    """
    try:
        is_connected = crud.test_db_connection(db)
        if is_connected:
            return {
                "status": "success",
                "message": "외부 데이터베이스 연결 성공",
                "connection": "43.203.24.147:13306/daepa_agent"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="외부 데이터베이스 연결에 실패했습니다."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database connection test error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"연결 테스트 중 오류가 발생했습니다: {str(e)}"
        )