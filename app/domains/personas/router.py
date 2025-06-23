"""
Persona 도메인 라우터
기존 app/routers/persona.py 내용을 도메인 구조에 맞게 이동
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import uuid
from datetime import datetime

from .database import get_persona_db, test_persona_db_connection
from .schemas import Persona, PersonaCreate, PersonaUpdate, PersonaListResponse
from . import crud
from app.security import get_current_active_user

logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter()

# 최신 user_id 조회 엔드포인트 (GET)
@router.get("/max-user-id")
async def get_max_user_id(
    db: Session = Depends(get_persona_db),
    current_user = Depends(get_current_active_user)
):
    """최신 user_id 조회 (자기 자신 참조를 위해)"""
    try:
        # 데이터베이스 연결 테스트
        if not crud.test_db_connection(db):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="외부 데이터베이스 연결에 실패했습니다."
            )
        
        # 최신 user_id 조회
        max_user_id = crud.get_max_user_id(db)
        
        logger.info(f"Retrieved max user_id: {max_user_id} by user {current_user.username}")
        return {
            "max_user_id": max_user_id,
            "next_user_id": (max_user_id or 0) + 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_max_user_id: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="최신 user_id 조회 중 오류가 발생했습니다."
        )

# 페르소나 생성 엔드포인트 (POST)
@router.post("", response_model=Persona, status_code=status.HTTP_201_CREATED)
async def create_persona(
    persona_data: PersonaCreate,
    db: Session = Depends(get_persona_db),
    current_user = Depends(get_current_active_user)
):
    """새 페르소나 생성"""
    try:
        # 데이터베이스 연결 테스트
        if not crud.test_db_connection(db):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="외부 데이터베이스 연결에 실패했습니다."
            )
        
        # user_id가 None인 경우 최신 user_id + 1로 설정 (자기 자신 참조)
        if persona_data.user_id is None:
            max_user_id = crud.get_max_user_id(db)
            next_user_id = (max_user_id or 0) + 1
            persona_data.user_id = next_user_id
            logger.info(f"Auto-assigned user_id: {next_user_id} (max_user_id was: {max_user_id})")
        else:
            logger.info(f"Using provided user_id: {persona_data.user_id}")
        
        # 페르소나 생성
        created_persona = crud.create_persona(db, persona_data, current_user.id)
        
        if not created_persona:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="페르소나 생성에 실패했습니다."
            )
        
        logger.info(f"Created new persona: {created_persona.name} (seq={created_persona.seq}) by user {current_user.username}")
        return created_persona
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_persona: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="페르소나 생성 중 오류가 발생했습니다."
        )

# 슬래시 없는 버전과 있는 버전 모두 지원 (슬래시 없는 버전을 먼저 등록)
@router.get("", response_model=List[Persona])
async def get_persona_list(
    skip: int = Query(0, ge=0, description="건너뛸 레코드 수"),
    limit: int = Query(1000, ge=1, le=1000, description="가져올 레코드 수"),
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

# 페이지네이션이 적용된 페르소나 목록 조회
@router.get("/paginated", response_model=PersonaListResponse)
async def get_persona_paginated(
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 항목 수"),
    search: Optional[str] = Query(None, description="검색어"),
    db: Session = Depends(get_persona_db),
    current_user = Depends(get_current_active_user)
):
    """페이지네이션이 적용된 페르소나 목록 조회"""
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

# 페르소나 단일 조회 엔드포인트 (GET)
@router.get("/{persona_seq}", response_model=Persona)
async def get_persona_by_seq(
    persona_seq: int,
    db: Session = Depends(get_persona_db),
    current_user = Depends(get_current_active_user)
):
    """seq로 특정 페르소나 조회"""
    try:
        # 데이터베이스 연결 테스트
        if not crud.test_db_connection(db):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="외부 데이터베이스 연결에 실패했습니다."
            )
        
        # 페르소나 조회
        persona = crud.get_persona_by_seq(db, persona_seq)
        
        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="페르소나를 찾을 수 없습니다."
            )
        
        logger.info(f"Retrieved persona: {persona.name} (seq={persona.seq}) by user {current_user.username}")
        return persona
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_persona_by_seq: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="페르소나 조회 중 오류가 발생했습니다."
        )

# 페르소나 상태 변경 엔드포인트 (PUT)
@router.put("/{persona_seq}/status", response_model=Persona)
async def update_persona_status(
    persona_seq: int,
    status: str = Query(..., regex="^(ACTIVE|INACTIVE)$", description="상태 (ACTIVE 또는 INACTIVE)"),
    db: Session = Depends(get_persona_db),
    current_user = Depends(get_current_active_user)
):
    """페르소나 상태 변경 (ACTIVE/INACTIVE)"""
    try:
        # 데이터베이스 연결 테스트
        if not crud.test_db_connection(db):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="외부 데이터베이스 연결에 실패했습니다."
            )
        
        # 페르소나 존재 확인
        existing_persona = crud.get_persona_by_seq(db, persona_seq)
        if not existing_persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="페르소나를 찾을 수 없습니다."
            )
        
        # 페르소나 상태 변경
        updated_persona = crud.update_persona_status(db, persona_seq, status)
        
        if not updated_persona:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="페르소나 상태 변경에 실패했습니다."
            )
        
        logger.info(f"Updated persona status: {updated_persona.name} (seq={updated_persona.seq}) -> {status} by user {current_user.username}")
        return updated_persona
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in update_persona_status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="페르소나 상태 변경 중 오류가 발생했습니다."
        )

# 페르소나 수정 엔드포인트 (PUT)
@router.put("/{persona_seq}", response_model=Persona)
async def update_persona(
    persona_seq: int,
    persona_data: PersonaUpdate,
    db: Session = Depends(get_persona_db),
    current_user = Depends(get_current_active_user)
):
    """페르소나 정보 수정"""
    try:
        # 데이터베이스 연결 테스트
        if not crud.test_db_connection(db):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="외부 데이터베이스 연결에 실패했습니다."
            )
        
        # 페르소나 존재 확인
        existing_persona = crud.get_persona_by_seq(db, persona_seq)
        if not existing_persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="페르소나를 찾을 수 없습니다."
            )
        
        # 페르소나 수정
        updated_persona = crud.update_persona(db, persona_seq, persona_data)
        
        if not updated_persona:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="페르소나 수정에 실패했습니다."
            )
        
        logger.info(f"Updated persona: {updated_persona.name} (seq={updated_persona.seq}) by user {current_user.username}")
        return updated_persona
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in update_persona: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="페르소나 수정 중 오류가 발생했습니다."
        )

# 페르소나 삭제 엔드포인트 (DELETE)
@router.delete("/{persona_seq}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_persona(
    persona_seq: int,
    db: Session = Depends(get_persona_db),
    current_user = Depends(get_current_active_user)
):
    """페르소나 삭제"""
    try:
        # 데이터베이스 연결 테스트
        if not crud.test_db_connection(db):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="외부 데이터베이스 연결에 실패했습니다."
            )
        
        # 페르소나 존재 확인
        existing_persona = crud.get_persona_by_seq(db, persona_seq)
        if not existing_persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="페르소나를 찾을 수 없습니다."
            )
        
        # 페르소나 삭제
        success = crud.delete_persona(db, persona_seq)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="페르소나 삭제에 실패했습니다."
            )
        
        logger.info(f"Deleted persona: {existing_persona.name} (seq={persona_seq}) by user {current_user.username}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in delete_persona: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="페르소나 삭제 중 오류가 발생했습니다."
        )

# 연결 테스트 엔드포인트
@router.get("/test/connection")
async def test_persona_db_connection_endpoint(
    db: Session = Depends(get_persona_db),
    current_user = Depends(get_current_active_user)
):
    """외부 데이터베이스 연결 테스트"""
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