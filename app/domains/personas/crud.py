"""
Persona 도메인 CRUD 함수들
외부 DB (t_persona 테이블) 조작 함수들
"""
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, func
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional
import logging
import json
from datetime import datetime

from .models import TPersona
from .schemas import PersonaCreate, PersonaUpdate

logger = logging.getLogger(__name__)

def test_db_connection(db: Session) -> bool:
    """데이터베이스 연결 테스트"""
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False

def get_personas(db: Session, skip: int = 0, limit: int = 1000, search: Optional[str] = None) -> List[TPersona]:
    """페르소나 목록 조회 - 강화된 검색"""
    try:
        query = db.query(TPersona)
        
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                or_(
                    TPersona.name.ilike(search_filter),
                    TPersona.id.ilike(search_filter),
                    TPersona.type.ilike(search_filter),
                    TPersona.status.ilike(search_filter),
                    TPersona.user_id.cast(db.String).ilike(search_filter),  # 사용자ID 검색 추가
                    TPersona.model_id.ilike(search_filter),
                    TPersona.summary.ilike(search_filter)
                )
            )
        
        return query.order_by(TPersona.seq.desc()).offset(skip).limit(limit).all()
        
    except Exception as e:
        logger.error(f"Error getting personas: {e}")
        return []

def get_personas_count(db: Session, search: Optional[str] = None) -> int:
    """페르소나 전체 개수 조회 (페이지네이션용)"""
    try:
        query = db.query(func.count(TPersona.seq))
        
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                or_(
                    TPersona.name.ilike(search_filter),
                    TPersona.id.ilike(search_filter),
                    TPersona.type.ilike(search_filter),
                    TPersona.status.ilike(search_filter),
                    TPersona.user_id.cast(db.String).ilike(search_filter),
                    TPersona.model_id.ilike(search_filter),
                    TPersona.summary.ilike(search_filter)
                )
            )
        
        return query.scalar() or 0
        
    except Exception as e:
        logger.error(f"Error counting personas: {e}")
        return 0

def get_max_user_id(db: Session) -> Optional[int]:
    """가장 높은 user_id 값 반환 (자기 자신 참조를 위해)"""
    try:
        result = db.query(func.max(TPersona.user_id)).scalar()
        return result
    except Exception as e:
        logger.error(f"Error getting max user_id: {e}")
        return None

def create_persona(db: Session, persona: PersonaCreate, created_by_user_id: int) -> Optional[TPersona]:
    """Raw SQL을 사용한 페르소나 생성 - properties NULL 보장"""
    try:
        # user_id 처리 (None인 경우 최신 user_id + 1로 설정)
        if persona.user_id is None:
            max_user_id = db.query(func.max(TPersona.user_id)).scalar()
            next_user_id = (max_user_id or 0) + 1
        else:
            next_user_id = persona.user_id
        
        # Raw SQL INSERT 쿼리 실행 - properties는 명시적으로 NULL
        insert_sql = text("""
            INSERT INTO t_persona (
                id, type, name, user_id, status, model_id, 
                tags, properties, summary, llm_prompt, chat_opening, background
            ) VALUES (
                :id, :type, :name, :user_id, :status, :model_id,
                :tags, NULL, :summary, :llm_prompt, :chat_opening, :background
            )
        """)
        
        # 파라미터 준비
        params = {
            'id': persona.id,
            'type': persona.type,
            'name': persona.name,
            'user_id': next_user_id,
            'status': persona.status,
            'model_id': persona.model_id,
            'tags': json.dumps(persona.tags) if persona.tags else None,
            # properties는 위 SQL에서 명시적으로 NULL로 설정
            'summary': persona.summary,
            'llm_prompt': persona.llm_prompt,
            'chat_opening': persona.chat_opening,
            'background': persona.background
        }
        
        logger.info(f"Creating persona with Raw SQL - properties will be NULL")
        
        # Raw SQL 실행
        result = db.execute(insert_sql, params)
        db.commit()
        
        # 생성된 레코드 조회 (LAST_INSERT_ID 사용)
        new_seq = result.lastrowid
        created_persona = db.query(TPersona).filter(TPersona.seq == new_seq).first()
        
        if created_persona:
            # 저장 후 실제 값 확인
            check_sql = text("SELECT properties, CHAR_LENGTH(properties) as len, properties IS NULL as is_null FROM t_persona WHERE seq = :seq")
            check_result = db.execute(check_sql, {"seq": new_seq}).fetchone()
            
            logger.info(f"Created persona with Raw SQL: {created_persona.name} (seq={created_persona.seq})")
            logger.info(f"Properties check: value={check_result.properties}, length={check_result.len}, is_null={check_result.is_null}")
            
            return created_persona
        else:
            logger.error("Failed to retrieve created persona")
            return None
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Raw SQL persona creation error: {e}")
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error in Raw SQL persona creation: {e}")
        return None

def get_persona_by_seq(db: Session, persona_seq: int) -> Optional[TPersona]:
    """seq로 특정 페르소나 조회"""
    try:
        return db.query(TPersona).filter(TPersona.seq == persona_seq).first()
    except Exception as e:
        logger.error(f"Error getting persona by seq {persona_seq}: {e}")
        return None

def get_persona_by_id(db: Session, persona_id: str) -> Optional[TPersona]:
    """id(UUID)로 특정 페르소나 조회"""
    try:
        return db.query(TPersona).filter(TPersona.id == persona_id).first()
    except Exception as e:
        logger.error(f"Error getting persona by id {persona_id}: {e}")
        return None

def update_persona(db: Session, persona_seq: int, persona_update: PersonaUpdate) -> Optional[TPersona]:
    """페르소나 정보 수정"""
    try:
        # 기존 페르소나 조회
        db_persona = db.query(TPersona).filter(TPersona.seq == persona_seq).first()
        if not db_persona:
            return None
        
        # 수정할 필드만 업데이트 (None이 아닌 값만)
        update_data = persona_update.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            if hasattr(db_persona, field):
                setattr(db_persona, field, value)
        
        # 수정 시간 업데이트는 DB에서 자동 처리됨 (ON UPDATE CURRENT_TIMESTAMP)
        
        db.commit()
        db.refresh(db_persona)
        
        logger.info(f"Updated persona: {db_persona.name} (seq={persona_seq})")
        return db_persona
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating persona seq {persona_seq}: {e}")
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error updating persona seq {persona_seq}: {e}")
        return None

def delete_persona(db: Session, persona_seq: int) -> bool:
    """페르소나 삭제"""
    try:
        # 기존 페르소나 조회
        db_persona = db.query(TPersona).filter(TPersona.seq == persona_seq).first()
        if not db_persona:
            return False
        
        # 페르소나 삭제
        db.delete(db_persona)
        db.commit()
        
        logger.info(f"Deleted persona: {db_persona.name} (seq={persona_seq})")
        return True
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error deleting persona seq {persona_seq}: {e}")
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error deleting persona seq {persona_seq}: {e}")
        return False

def update_persona_status(db: Session, persona_seq: int, status: str) -> Optional[TPersona]:
    """페르소나 상태 변경 (ACTIVE/INACTIVE)"""
    try:
        db_persona = db.query(TPersona).filter(TPersona.seq == persona_seq).first()
        if not db_persona:
            return None
        
        db_persona.status = status
        db.commit()
        db.refresh(db_persona)
        
        logger.info(f"Updated persona status: {db_persona.name} (seq={persona_seq}) -> {status}")
        return db_persona
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating persona status seq {persona_seq}: {e}")
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error updating persona status seq {persona_seq}: {e}")
        return None

def get_personas_by_status(db: Session, status: str, skip: int = 0, limit: int = 100) -> List[TPersona]:
    """상태별 페르소나 목록 조회"""
    try:
        return (
            db.query(TPersona)
            .filter(TPersona.status == status)
            .order_by(TPersona.seq.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    except Exception as e:
        logger.error(f"Error getting personas by status {status}: {e}")
        return []

def get_personas_by_type(db: Session, persona_type: str, skip: int = 0, limit: int = 100) -> List[TPersona]:
    """타입별 페르소나 목록 조회"""
    try:
        return (
            db.query(TPersona)
            .filter(TPersona.type == persona_type)
            .order_by(TPersona.seq.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    except Exception as e:
        logger.error(f"Error getting personas by type {persona_type}: {e}")
        return []

def get_personas_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[TPersona]:
    """사용자별 페르소나 목록 조회"""
    try:
        return (
            db.query(TPersona)
            .filter(TPersona.user_id == user_id)
            .order_by(TPersona.seq.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    except Exception as e:
        logger.error(f"Error getting personas by user {user_id}: {e}")
        return []