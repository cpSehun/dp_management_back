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

def convert_prompt_response(db_prompt):
    """프롬프트 응답 변환 헬퍼 함수"""
    if not db_prompt:
        return None
        
    # 메인 프롬프트의 created_by 변환 (현재 버전 생성자로)
    current_version = None
    for version in db_prompt.versions:
        if version.version == db_prompt.version:
            current_version = version
            break
    
    # 현재 활성 버전의 생성자를 메인 created_by로 설정
    if current_version and current_version.created_by_user:
        db_prompt.created_by = current_version.created_by_user.username
    elif db_prompt.created_by_user:
        db_prompt.created_by = db_prompt.created_by_user.username
    else:
        db_prompt.created_by = None
        
    # 각 버전의 created_by 변환
    for version in db_prompt.versions:
        if hasattr(version, 'created_by_user') and version.created_by_user:
            version.created_by = version.created_by_user.username
        else:
            version.created_by = None
    
    return db_prompt

@router.post("", response_model=schemas.ImagePromptResponse, status_code=status.HTTP_201_CREATED)
def create_new_image_prompt(
    request: Request,
    prompt_in: schemas.ImagePromptCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    print(f"Backend: Image prompt creation request received for URL: {request.url.path}")
    print(f"Backend: Image prompt request body: {prompt_in.model_dump_json(indent=2)}")

    new_prompt = crud.create_image_prompt(db=db, prompt_in=prompt_in, user_id=current_user.id)
    db_prompt_with_user = crud.get_image_prompt(db, prompt_id=new_prompt.id)
    
    converted_prompt = convert_prompt_response(db_prompt_with_user)
    return converted_prompt

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
    
    # 각 프롬프트 변환
    converted_prompts = []
    for prompt in prompts_from_db:
        converted_prompt = convert_prompt_response(prompt)
        if converted_prompt:
            converted_prompts.append(converted_prompt)
    
    return schemas.PaginatedImagePromptsResponse(
        total_items=total_items,
        items=converted_prompts
    )

@router.get("/{prompt_id}", response_model=schemas.ImagePromptResponse)
async def read_single_image_prompt(prompt_id: int, db: Session = Depends(get_db)):
    db_prompt = crud.get_image_prompt(db, prompt_id=prompt_id)
    if db_prompt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image prompt not found")
    
    converted_prompt = convert_prompt_response(db_prompt)
    return converted_prompt

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
    
    db_prompt_with_user = crud.get_image_prompt(db, prompt_id=prompt_id)
    converted_prompt = convert_prompt_response(db_prompt_with_user)
    return converted_prompt


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
    db_prompt_with_user = crud.get_image_prompt(db, prompt_id=prompt_id)
    converted_prompt = convert_prompt_response(db_prompt_with_user)
    return converted_prompt

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
    
    # 각 버전의 created_by를 username으로 변환
    for version in versions:
        if hasattr(version, 'created_by_user') and version.created_by_user:
            version.created_by = version.created_by_user.username
        else:
            version.created_by = None
    
    return versions
