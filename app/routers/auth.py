from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import schemas, security, crud, database

router = APIRouter()

@router.post("/login", response_model=schemas.Token)
def login(user_login: schemas.UserLogin, db: Session = Depends(database.get_db)):
    user = crud.authenticate_user(db, user_login.username, user_login.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    access_token = security.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"} 