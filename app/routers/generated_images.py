from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional

from .. import schemas, crud, models
from ..database import get_db
from ..security import get_current_active_user

router = APIRouter(
    prefix="/api/v1/images",
    tags=["Generated Images"],
)

def convert_generated_image_response(db_image):
    """생성된 이미지 응답 변환 헬퍼 함수"""
    if not db_image:
        return None
        
    # created_by를 username으로 변환
    if db_image.user:  # created_by_user에서 user로 변경
        db_image.created_by = db_image.user.username
    else:
        db_image.created_by = None
    
    return db_image

@router.post("/metadata/save", response_model=schemas.GeneratedImageResponse, status_code=status.HTTP_201_CREATED)
def save_generated_image_metadata(
    request: Request,
    image_in: schemas.GeneratedImageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """생성된 이미지 메타데이터를 DB에 저장"""
    print(f"Backend: Generated image metadata save request received for URL: {request.url.path}")
    print(f"Backend: Generated image request body: {image_in.model_dump_json(indent=2)}")
    print(f"Backend: Current user: {current_user.username if current_user else 'None'}")

    try:
        # 새 이미지 메타데이터 저장
        print("Backend: Creating generated image...")
        new_image = crud.create_generated_image(db=db, image_in=image_in, user_id=current_user.id)
        print(f"Backend: Image created with ID: {new_image.id}")
        
        # 생성 후 사용자 정보를 포함해서 다시 조회
        print("Backend: Fetching image with user info...")
        db_image_with_user = crud.get_generated_image(db, image_id=new_image.id)
        print(f"Backend: Image fetched: {db_image_with_user.name if db_image_with_user else 'None'}")
        
        converted_image = convert_generated_image_response(db_image_with_user)
        print("Backend: Image response converted successfully")
        return converted_image
        
    except Exception as e:
        print(f"Backend: Error saving image metadata: {str(e)}")
        print(f"Backend: Error type: {type(e).__name__}")
        import traceback
        print(f"Backend: Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save image metadata: {str(e)}"
        )

@router.get("", response_model=schemas.PaginatedGeneratedImagesResponse)
async def read_all_generated_images(
    skip: int = 0, 
    limit: int = 10, 
    search: Optional[str] = Query(None, alias="searchTerm"),
    db: Session = Depends(get_db)
):
    """생성된 이미지 목록 조회 (모든 사용자)"""
    images_from_db = crud.get_generated_images(db, skip=skip, limit=limit, search_term=search)
    total_items = crud.get_generated_images_count(db, search_term=search)
    
    # 각 이미지 변환
    converted_images = []
    for image in images_from_db:
        converted_image = convert_generated_image_response(image)
        if converted_image:
            converted_images.append(converted_image)
    
    return schemas.PaginatedGeneratedImagesResponse(
        total_items=total_items,
        items=converted_images
    )

@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_generated_image(
    image_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """생성된 이미지 삭제 (최고관리자 전용)"""
    # 최고관리자 권한 체크
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="최고관리자만 이미지를 삭제할 수 있습니다."
        )
    
    db_image = crud.get_generated_image(db, image_id=image_id)
    if not db_image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated image not found")
    
    deleted_image = crud.delete_generated_image(db, image_id=image_id)
    if not deleted_image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated image not found")
    
    return None