"""
Persona 도메인 라우터
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from .database import get_persona_db, test_persona_db_connection
from .schemas import Persona, PersonaCreate, PersonaUpdate, PersonaListResponse
from . import crud
from app.security import get_current_active_user
from app.domains.users.models import User

logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter()

@router.get("/", response_model=List[Persona])
async def get_persona_list(
    skip: int = Query(0, ge=0, description="건너뛸 레코드 수"),
    limit: int = Query(20, ge=1, le=100, description="가져올 레코드 수"),
    search: Optional[str] = Query(None, description="검색어 (이름, ID, 타입, 상태 등)"),
    db: Session = Depends(get_persona_db),
    current_user: User = Depends(get_current_active_user)
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
    current_user: models.User = Depends(get_current_active_user)
):
    """
    페이지네이션이 적용된 페르소나 목록 조회
    
    - **page**: 페이지 번호 (1부터 시작)
    - **limit**: 페이지당 항목 수 (기본값: 20, 최대: 100)
    - **search**: 검색어 (선택사항)
    
    전체 항목 수와 함께 페이지네이션 정보를 반환합니다.
    """
    try:
        # 데이터베이스 연결 테스트
        if not test_db_connection(db):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="외부 데이터베이스 연결에 실패했습니다."
            )
        
        # skip 계산
        skip = (page - 1) * limit
        
        # 총 개수 및 목록 조회
        total_items = get_personas_count(db, search=search)
        personas = get_personas(db, skip=skip, limit=limit, search=search)
        
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

@router.get("/{seq}", response_model=Persona)
async def get_persona_detail(
    seq: int,
    db: Session = Depends(get_persona_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    특정 페르소나 상세 정보 조회
    
    - **seq**: 페르소나 시퀀스 번호
    """
    try:
        persona = get_persona_by_seq(db, seq=seq)
        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="페르소나를 찾을 수 없습니다."
            )
        
        logger.info(f"Retrieved persona detail: seq={seq}, name={persona.name}")
        return persona
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_persona_detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="페르소나 정보를 가져오는 중 오류가 발생했습니다."
        )

@router.post("/", response_model=Persona, status_code=status.HTTP_201_CREATED)
async def create_persona_endpoint(
    persona: PersonaCreate,
    db: Session = Depends(get_persona_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    새 페르소나 생성
    
    관리자 권한이 필요할 수 있습니다. (현재는 로그인한 사용자 모두 가능)
    """
    try:
        # 데이터베이스 연결 테스트
        if not test_db_connection(db):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="외부 데이터베이스 연결에 실패했습니다."
            )
        
        # 페르소나 생성
        created_persona = create_persona(db, persona=persona)
        if not created_persona:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="페르소나 생성에 실패했습니다."
            )
        
        logger.info(f"Created new persona: seq={created_persona.seq}, name={created_persona.name} by user {current_user.username}")
        return created_persona
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_persona_endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="페르소나 생성 중 오류가 발생했습니다."
        )

@router.put("/{seq}", response_model=Persona)
async def update_persona_endpoint(
    seq: int,
    persona_update: PersonaUpdate,
    db: Session = Depends(get_persona_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    페르소나 정보 업데이트
    
    - **seq**: 업데이트할 페르소나 시퀀스 번호
    """
    try:
        # 기존 페르소나 존재 확인
        existing_persona = get_persona_by_seq(db, seq=seq)
        if not existing_persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="페르소나를 찾을 수 없습니다."
            )
        
        # 페르소나 업데이트
        updated_persona = update_persona(db, seq=seq, persona_update=persona_update)
        if not updated_persona:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="페르소나 업데이트에 실패했습니다."
            )
        
        logger.info(f"Updated persona: seq={seq}, name={updated_persona.name} by user {current_user.username}")
        return updated_persona
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in update_persona_endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="페르소나 업데이트 중 오류가 발생했습니다."
        )

@router.delete("/{seq}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_persona_endpoint(
    seq: int,
    db: Session = Depends(get_persona_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    페르소나 삭제
    
    - **seq**: 삭제할 페르소나 시퀀스 번호
    
    관리자 권한이 필요할 수 있습니다. (현재는 로그인한 사용자 모두 가능)
    """
    try:
        # 기존 페르소나 존재 확인
        existing_persona = get_persona_by_seq(db, seq=seq)
        if not existing_persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="페르소나를 찾을 수 없습니다."
            )
        
        # 페르소나 삭제
        deleted = delete_persona(db, seq=seq)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="페르소나 삭제에 실패했습니다."
            )
        
        logger.info(f"Deleted persona: seq={seq}, name={existing_persona.name} by user {current_user.username}")
        return None  # 204 No Content
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in delete_persona_endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="페르소나 삭제 중 오류가 발생했습니다."
        )

@router.get("/test/connection")
async def test_persona_db_connection_endpoint(
    db: Session = Depends(get_persona_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    외부 데이터베이스 연결 테스트
    
    개발/디버깅 목적으로 사용됩니다.
    """
    try:
        is_connected = test_db_connection(db)
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