"""
Persona 도메인 CRUD 함수들
외부 DB (t_persona 테이블) 조작 함수들
"""
from sqlalchemy.orm import Session
from sqlalchemy import text, or_
from typing import List, Optional
import logging

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
                    TPersona.user_id.cast(db.String).ilike(search_filter),  # 🔥 사용자ID 검색 추가
                    TPersona.model_id.ilike(search_filter),
                    TPersona.summary.ilike(search_filter)
                )
            )
        
        return query.order_by(TPersona.seq.desc()).offset(skip).limit(limit).all()
        
    except Exception as e:
        logger.error(f"Error getting personas: {e}")
        return []

def get_personas_count(db: Session, search: Optional[str] = None) -> int:
    """페르소나 총 개수 - 강화된 검색"""
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
                    TPersona.user_id.cast(db.String).ilike(search_filter),  # 🔥 사용자ID 검색 추가
                    TPersona.model_id.ilike(search_filter),
                    TPersona.summary.ilike(search_filter)
                )
            )
        
        return query.count()
        
    except Exception as e:
        logger.error(f"Error getting personas count: {e}")
        return 0

def get_persona_by_seq(db: Session, seq: int) -> Optional[TPersona]:
    """시퀀스로 페르소나 조회"""
    try:
        return db.query(TPersona).filter(TPersona.seq == seq).first()
    except Exception as e:
        logger.error(f"Error getting persona by seq {seq}: {e}")
        return None

def create_persona(db: Session, persona: PersonaCreate) -> Optional[TPersona]:
    """새 페르소나 생성"""
    try:
        db_persona = TPersona(
            name=persona.name,
            type=persona.type,
            status=persona.status,
            id=persona.id,
            user_id=persona.user_id,
            model_id=persona.model_id,
            tags=persona.tags,
            properties=persona.properties,
            summary=persona.summary,
            llm_prompt=persona.llm_prompt,
            chat_opening=persona.chat_opening,
            background=persona.background
        )
        
        db.add(db_persona)
        db.commit()
        db.refresh(db_persona)
        return db_persona
        
    except Exception as e:
        logger.error(f"Error creating persona: {e}")
        db.rollback()
        return None

def update_persona(db: Session, seq: int, persona_update: PersonaUpdate) -> Optional[TPersona]:
    """페르소나 업데이트"""
    try:
        db_persona = db.query(TPersona).filter(TPersona.seq == seq).first()
        if not db_persona:
            return None
        
        update_data = persona_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_persona, field, value)
        
        db.commit()
        db.refresh(db_persona)
        return db_persona
        
    except Exception as e:
        logger.error(f"Error updating persona seq {seq}: {e}")
        db.rollback()
        return None

def delete_persona(db: Session, seq: int) -> bool:
    """페르소나 삭제"""
    try:
        db_persona = db.query(TPersona).filter(TPersona.seq == seq).first()
        if not db_persona:
            return False
        
        db.delete(db_persona)
        db.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error deleting persona seq {seq}: {e}")
        db.rollback()
        return False