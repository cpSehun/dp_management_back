from sqlalchemy.orm import Session
from app import models, schemas, security # security 모듈 임포트

# 사용자 ID로 사용자 조회
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

# 이메일로 사용자 조회
def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

# 사용자 이름으로 사용자 조회
def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

# 여러 사용자 조회 (페이징 처리)
def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

# 사용자 생성
def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = security.get_password_hash(user.password) # 비밀번호 해싱
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# 사용자 인증 (로그인)
def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username=username)
    if not user:
        return None
    if not security.verify_password(password, user.hashed_password):
        return None
    return user

# 여기에 다른 모델(예: Prompt)에 대한 CRUD 함수 추가 가능 