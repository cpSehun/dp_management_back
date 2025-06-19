# app/routers/workflow_prompts.py

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.database import get_db
from app.security import get_current_active_user
from app import models, schemas, crud

logger = logging.getLogger(__name__)

router = APIRouter()

# 두 가지 경로를 모두 처리하도록 설정
@router.get("/", response_model=schemas.PaginatedWorkflowPrompts)
@router.get("", response_model=schemas.PaginatedWorkflowPrompts)
async def get_workflow_prompts(
    skip: int = Query(0, ge=0, description="건너뛸 항목 수"),
    limit: int = Query(100, ge=1, le=1000, description="가져올 최대 항목 수"),
    search: Optional[str] = Query(None, description="검색어"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """워크플로우 프롬프트 목록 조회"""
    try:
        prompts = crud.get_workflow_prompts(db, skip=skip, limit=limit, search_term=search)
        total_count = crud.get_workflow_prompts_count(db, search_term=search)
        
        return schemas.PaginatedWorkflowPrompts(
            total_items=total_count,
            items=prompts
        )
    except Exception as e:
        logger.error(f"워크플로우 프롬프트 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="프롬프트 목록을 가져오는 중 오류가 발생했습니다")

@router.get("/latest", response_model=schemas.LatestPromptResponse)
async def get_latest_workflow_prompt(
    category: Optional[str] = Query(None, description="프롬프트 카테고리"),  # ✅ 추가
    type: Optional[str] = Query(None, description="프롬프트 타입 (CHAR/STORY)"),
    db: Session = Depends(get_db)
):
    """최신 워크플로우 프롬프트 조회 (페르소나 생성 시 사용)"""
    try:
        prompt = crud.get_latest_workflow_prompt(db, category=category, type=type)  # ✅ category 추가
        if not prompt:
            raise HTTPException(
                status_code=404, 
                detail=f"프롬프트를 찾을 수 없습니다."
            )
        
        return schemas.LatestPromptResponse(
            id=prompt.id,
            name=prompt.name,
            category=prompt.category,  # ✅ category 반환
            type=prompt.type,
            llm_prompt=prompt.llm_prompt,
            version=prompt.version
        )
    except Exception as e:
        logger.error(f"최신 워크플로우 프롬프트 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="프롬프트 조회 중 오류가 발생했습니다")


@router.get("/{prompt_id}", response_model=schemas.WorkflowPrompt)
async def get_workflow_prompt(
    prompt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """워크플로우 프롬프트 상세 조회"""
    try:
        prompt = crud.get_workflow_prompt(db, prompt_id=prompt_id)
        if not prompt:
            raise HTTPException(status_code=404, detail="프롬프트를 찾을 수 없습니다")
        
        return prompt
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"프롬프트 상세 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="프롬프트를 가져오는 중 오류가 발생했습니다")

@router.put("/{prompt_id}", response_model=schemas.WorkflowPrompt)
async def update_workflow_prompt(
    prompt_id: int,
    prompt_update: schemas.WorkflowPromptUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """워크플로우 프롬프트 수정 (새 버전 생성)"""
    try:
        updated_prompt = crud.update_workflow_prompt(
            db, 
            prompt_id=prompt_id, 
            prompt_in=prompt_update, 
            user_id=current_user.id
        )
        if not updated_prompt:
            raise HTTPException(status_code=404, detail="프롬프트를 찾을 수 없습니다")
        
        logger.info(f"프롬프트 업데이트: ID {prompt_id}, 새 버전: {updated_prompt.version}")
        return updated_prompt
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"프롬프트 수정 오류: {e}")
        raise HTTPException(status_code=500, detail="프롬프트 수정 중 오류가 발생했습니다")

@router.post("/{prompt_id}/rollback/{target_version}", response_model=schemas.WorkflowPrompt)
async def rollback_workflow_prompt(
    prompt_id: int,
    target_version: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """워크플로우 프롬프트 버전 롤백"""
    try:
        rolled_back_prompt = crud.rollback_workflow_prompt(
            db, 
            prompt_id=prompt_id, 
            target_version=target_version, 
            user_id=current_user.id
        )
        if not rolled_back_prompt:
            raise HTTPException(status_code=404, detail="프롬프트 또는 대상 버전을 찾을 수 없습니다")
        
        logger.info(f"프롬프트 롤백: ID {prompt_id}, 버전 {target_version}로 복원")
        return rolled_back_prompt
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"프롬프트 롤백 오류: {e}")
        raise HTTPException(status_code=500, detail="프롬프트 롤백 중 오류가 발생했습니다")
