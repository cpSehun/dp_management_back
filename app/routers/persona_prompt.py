from pickletools import read_uint1
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional

from .. import schemas, crud, models
from ..database import get_db
from ..security import get_current_active_user

router = APIRouter(
    prefix="/api/v1/prompts/persona",
    tags=["Persona Prompts"],
)

def convert_persona_prompt_response(db_prompt):
    """페르소나 프롬프트 응답 변환 헬퍼 함수"""
    if not db_prompt:
        return None
        
    # 현재 활성 버전 찾기
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

@router.post("", response_model=schemas.PersonaPromptResponse, status_code=status.HTTP_201_CREATED)
def create_new_persona_prompt(
    request: Request,
    prompt_in: schemas.PersonaPromptCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    print(f"Backend: Persona prompt creation request received for URL: {request.url.path}")
    print(f"Backend: Persona prompt request body: {prompt_in.model_dump_json(indent=2)}")

    # 새 프롬프트 생성
    new_prompt = crud.create_persona_prompt(db=db, prompt_in=prompt_in, user_id=current_user.id)
    
    # 생성 후 사용자 정보를 포함해서 다시 조회
    db_prompt_with_user = crud.get_persona_prompt(db, prompt_id=new_prompt.id)
    
    converted_prompt = convert_persona_prompt_response(db_prompt_with_user)
    return converted_prompt

@router.get("", response_model=schemas.PaginatedPersonaPromptsResponse)
async def read_all_persona_prompts(
    skip: int = 0, 
    limit: int = 10, 
    search: Optional[str] = Query(None, alias="searchTerm"),
    db: Session = Depends(get_db)
):
    prompts_from_db = crud.get_persona_prompts(db, skip=skip, limit=limit, search_term=search)
    total_items = crud.get_persona_prompts_count(db, search_term=search)
    
    # 각 프롬프트 변환
    converted_prompts = []
    for prompt in prompts_from_db:
        converted_prompt = convert_persona_prompt_response(prompt)
        if converted_prompt:
            converted_prompts.append(converted_prompt)
    
    return schemas.PaginatedPersonaPromptsResponse(
        total_items=total_items,
        items=converted_prompts
    )

@router.get("/{prompt_id}", response_model=schemas.PersonaPromptResponse)
async def read_single_persona_prompt(prompt_id: int, db: Session = Depends(get_db)):
    db_prompt = crud.get_persona_prompt(db, prompt_id=prompt_id)
    if db_prompt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona prompt not found")
    
    convert_prompt = convert_persona_prompt_response(db_prompt)
    return convert_prompt

@router.put("/{prompt_id}", response_model=schemas.PersonaPromptResponse)
async def update_single_persona_prompt(
    prompt_id: int, 
    prompt_update_data: schemas.PersonaPromptUpdate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    updated_prompt = crud.update_persona_prompt(
        db, 
        prompt_id=prompt_id, 
        prompt_in=prompt_update_data,
        user_id=current_user.id
    )
    if updated_prompt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona prompt not found")
    
    
    db_prompt_with_user = crud.get_persona_prompt(db, prompt_id=prompt_id)
    converted_prompt = convert_persona_prompt_response(db_prompt_with_user)
    return converted_prompt

@router.put("/{prompt_id}/rollback/{version}", response_model=schemas.PersonaPromptResponse)
async def rollback_persona_prompt(
    prompt_id: int,
    version: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    updated_prompt = crud.rollback_persona_prompt(
        db=db, 
        prompt_id=prompt_id, 
        target_version=version,
        user_id=current_user.id
    )
    if not updated_prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Persona prompt or version not found for rollback."
        )
    db_prompt_with_user = crud.get_persona_prompt(db, prompt_id=prompt_id)
    converted_prompt = convert_persona_prompt_response(db_prompt_with_user)
    return converted_prompt

@router.get("/{prompt_id}/versions", response_model=List[schemas.PersonaPromptVersionInDB])
async def get_persona_prompt_versions(
    prompt_id: int,
    db: Session = Depends(get_db)
):
    db_prompt = crud.get_persona_prompt(db, prompt_id)
    if not db_prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona prompt not found")
    
    versions = sorted(db_prompt.versions, key=lambda x: x.version, reverse=True)
    
    # versions의 created_by를 username으로 변환
    for version in versions:
        if hasattr(version, 'created_by_user') and version.created_by_user:
            version.created_by = version.created_by_user.username
        else:
            version.created_by = None
            
    return versions