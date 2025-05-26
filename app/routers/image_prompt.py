from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional

from .. import schemas, crud, models
from ..database import get_db
from ..security import get_current_active_user

router = APIRouter(
    prefix="/api/v1/prompts/image",
    tags=["Image Prompts"],
)

@router.post("", response_model=schemas.ImagePromptResponse, status_code=status.HTTP_201_CREATED)
def create_new_image_prompt(
    request: Request,
    prompt_in: schemas.ImagePromptCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    print(f"Backend: Image prompt creation request received for URL: {request.url.path}")
    print(f"Backend: Image prompt request body: {prompt_in.model_dump_json(indent=2)}")

    # 새 프롬프트 생성 (v1으로 자동 시작)
    new_prompt = crud.create_image_prompt(db=db, prompt_in=prompt_in, user_id=current_user.id)
    return new_prompt

@router.get("", response_model=schemas.PaginatedImagePromptsResponse)
async def read_all_image_prompts(
    skip: int = 0, 
    limit: int = 10, 
    search: Optional[str] = Query(None, alias="searchTerm"),
    db: Session = Depends(get_db)
):
    # prompts 테이블에서 직접 조회 (현재 활성 프롬프트만)
    prompts_from_db = crud.get_image_prompts(db, skip=skip, limit=limit, search_term=search)
    total_items = crud.get_image_prompts_count(db, search_term=search)
    
    return schemas.PaginatedImagePromptsResponse(
        total_items=total_items,
        items=prompts_from_db  # 직접 반환
    )

@router.get("/{prompt_id}", response_model=schemas.ImagePromptResponse)
async def read_single_image_prompt(prompt_id: int, db: Session = Depends(get_db)):
    db_prompt = crud.get_image_prompt(db, prompt_id=prompt_id)
    if db_prompt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image prompt not found")
    return db_prompt

@router.put("/{prompt_id}", response_model=schemas.ImagePromptResponse)
async def update_single_image_prompt(
    prompt_id: int, 
    prompt_update_data: schemas.ImagePromptUpdate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    updated_prompt = crud.update_image_prompt(
        db, 
        prompt_id=prompt_id, 
        prompt_in=prompt_update_data,
        user_id=current_user.id
    )
    if updated_prompt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image prompt not found")
    return updated_prompt

@router.put("/{prompt_id}/rollback/{version}", response_model=schemas.ImagePromptResponse)
async def rollback_image_prompt(
    prompt_id: int,
    version: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """지정된 버전으로 프롬프트 롤백"""
    updated_prompt = crud.rollback_image_prompt(
        db=db, 
        prompt_id=prompt_id, 
        target_version=version,
        user_id=current_user.id
    )
    if not updated_prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Image prompt or version not found for rollback."
        )
    return updated_prompt

@router.get("/{prompt_id}/versions", response_model=List[schemas.ImagePromptVersionInDB])
async def get_image_prompt_versions(
    prompt_id: int,
    db: Session = Depends(get_db)
):
    """프롬프트의 모든 버전 히스토리 조회"""
    db_prompt = crud.get_image_prompt(db, prompt_id)
    if not db_prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image prompt not found")
    
    # 버전 히스토리를 최신순으로 정렬하여 반환
    versions = sorted(db_prompt.versions, key=lambda x: x.version, reverse=True)
    return versions
