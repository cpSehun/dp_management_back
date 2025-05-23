from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional

# 경로가 app 폴더를 기준으로 하므로 .. 을 사용합니다.
from .. import schemas, crud, models # crud에서 ImagePrompt CRUD 함수들을 가져옵니다.
from ..database import get_db
from ..security import get_current_active_user # auth.py 대신 security.py에서 가져오도록 수정

router = APIRouter(
    prefix="/api/v1/prompts/image",
    tags=["Image Prompts"],
    # dependencies=[Depends(get_current_active_user)] # 모든 라우트에 인증 적용 시
)

# ORM 객체의 tags 문자열을 리스트로 변환하는 헬퍼 함수
def _convert_orm_tags_to_list(prompt_orm: models.ImagePrompt) -> models.ImagePrompt:
    print(f"Before conversion - ID: {prompt_orm.id if hasattr(prompt_orm, 'id') else 'N/A'}, Tags: {prompt_orm.tags if hasattr(prompt_orm, 'tags') else 'N/A'}, Type: {type(prompt_orm.tags) if hasattr(prompt_orm, 'tags') else 'N/A'}")
    if prompt_orm and hasattr(prompt_orm, 'tags') and isinstance(prompt_orm.tags, str):
        prompt_orm.tags = [tag.strip() for tag in prompt_orm.tags.split(',') if tag.strip()]
    elif prompt_orm and hasattr(prompt_orm, 'tags') and prompt_orm.tags is None:
        prompt_orm.tags = []
    elif prompt_orm and not hasattr(prompt_orm, 'tags'):
        prompt_orm.tags = []
    print(f"After conversion - ID: {prompt_orm.id if hasattr(prompt_orm, 'id') else 'N/A'}, Tags: {prompt_orm.tags if hasattr(prompt_orm, 'tags') else 'N/A'}, Type: {type(prompt_orm.tags) if hasattr(prompt_orm, 'tags') else 'N/A'}")
    return prompt_orm

@router.post("", response_model=schemas.ImagePromptResponse)
def create_new_image_prompt(
    request: Request,
    prompt_in: schemas.ImagePromptCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    print(f"Backend: Image prompt creation request received for URL: {request.url.path}")
    print(f"Backend: Image prompt request body: {prompt_in.model_dump_json(indent=2)}")

    # 첫 번째 버전을 필수로 활성화
    if not prompt_in.versions:
        raise HTTPException(status_code=400, detail="At least one version is required.")
    if not any(v.is_active for v in prompt_in.versions):
        prompt_in.versions[0].is_active = True

    # 사용자 ID를 전달하여 created_by 필드 설정
    new_prompt = crud.create_image_prompt(db=db, prompt_in=prompt_in, user_id=current_user.id)
    
    # 태그를 문자열에서 리스트로 변환
    return _convert_orm_tags_to_list(new_prompt)

@router.get("", response_model=schemas.PaginatedImagePromptsResponse)
async def read_all_image_prompts(
    skip: int = 0, 
    limit: int = 10, 
    search: Optional[str] = Query(None, alias="searchTerm"),
    db: Session = Depends(get_db)
):
    prompts_from_db = crud.get_image_prompts(db, skip=skip, limit=limit, search_term=search)
    total_items = crud.get_image_prompts_count(db, search_term=search)
    processed_prompts = [_convert_orm_tags_to_list(p) for p in prompts_from_db]
    return schemas.PaginatedImagePromptsResponse(
        total_items=total_items,
        items=processed_prompts
    )

@router.get("/{prompt_id}", response_model=schemas.ImagePromptResponse)
async def read_single_image_prompt(prompt_id: int, db: Session = Depends(get_db)):
    db_prompt_orm = crud.get_image_prompt(db, prompt_id=prompt_id)
    if db_prompt_orm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image prompt not found")
    return _convert_orm_tags_to_list(db_prompt_orm)

@router.put("/{prompt_id}", response_model=schemas.ImagePromptResponse)
async def update_single_image_prompt(
    prompt_id: int, 
    prompt_update_data: schemas.ImagePromptUpdate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    updated_prompt_orm = crud.update_image_prompt(
        db, 
        prompt_id=prompt_id, 
        prompt_update_data=prompt_update_data,
        user_id=current_user.id
    )
    if updated_prompt_orm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image prompt not found")
    return _convert_orm_tags_to_list(updated_prompt_orm)

@router.delete("/{prompt_id}", response_model=schemas.ImagePromptResponse)
async def delete_single_image_prompt(
    prompt_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    deleted_prompt_orm = crud.delete_image_prompt(db, prompt_id=prompt_id)
    if deleted_prompt_orm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image prompt not found")
    return _convert_orm_tags_to_list(deleted_prompt_orm)

# --- Image Prompt Version Routes ---
@router.post("/{prompt_id}/versions", response_model=schemas.ImagePromptVersionInDB, status_code=status.HTTP_201_CREATED)
async def add_new_version_to_image_prompt(
    prompt_id: int,
    version_data: schemas.ImagePromptVersionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    db_prompt_check = crud.get_image_prompt(db, prompt_id=prompt_id)
    if not db_prompt_check:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image prompt not found to add version.")
    
    # 사용자 ID를 전달하여 created_by 필드 설정
    new_version = crud.create_image_prompt_version(
        db=db, 
        prompt_id=prompt_id, 
        version_data=version_data,
        user_id=current_user.id
    )
    return new_version

@router.put("/{prompt_id}/versions/{version_id}/activate", response_model=schemas.ImagePromptResponse)
async def activate_image_prompt_version(
    prompt_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    updated_prompt_orm = crud.set_active_image_version(db=db, prompt_id=prompt_id, version_id=version_id)
    if not updated_prompt_orm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image prompt or version not found for activation.")
    return _convert_orm_tags_to_list(updated_prompt_orm) 