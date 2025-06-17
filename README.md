## 어드민 계정 생성
docker exec -it dp_management_backend_dev python create_admin.py

# DP 관리 시스템 - 백엔드

FastAPI와 SQLAlchemy로 구현된 DP 관리 시스템의 백엔드입니다.

## 기술 스택

- FastAPI
- SQLAlchemy
- MySQL
- OAuth 2.0 (Google 로그인)
- JWT 인증

## 설치 및 실행

### 로컬 개발 환경

```bash
# 패키지 설치
pip install -r requirements.txt

# 개발 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker 환경

```bash
# Docker 이미지 빌드 & 실행
docker-compose up --build -d
```

### Docker Compose 환경

```bash
# 전체 시스템 실행 (프론트엔드 및 DB 포함)
docker-compose up -d
```

## DB 마이그레이션

```bash
# Alembic으로 마이그레이션 생성
alembic revision --autogenerate -m "Initial migration"

# 마이그레이션 실행
alembic upgrade head
```

## 프로젝트 구조

```
backend/
├── app/
│   ├── api/
│   │   └── v1/         # API 버전 1
│   ├── core/           # 설정, 보안, 의존성 등
│   ├── crud/           # 데이터베이스 CRUD 작업
│   ├── db/             # 데이터베이스 관련 코드
│   ├── models/         # SQLAlchemy 모델 정의
│   ├── routers/        # API 라우터
│   ├── schemas/        # Pydantic 스키마
│   └── main.py         # 애플리케이션 진입점
├── alembic/            # 데이터베이스 마이그레이션
└── requirements.txt    # 패키지 의존성
```

## API 문서

FastAPI는 자동으로 Swagger UI와 ReDoc 문서를 생성합니다:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 환경 변수

`.env` 파일에 다음 환경 변수를 설정하세요:

```
MYSQL_USER=root
MYSQL_PASSWORD=password
MYSQL_HOST=db
MYSQL_PORT=3306
MYSQL_DATABASE=dp_management
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
```

## 사용자 생성 및 인증

### 사용자 생성

```bash
curl -X POST "http://localhost:8000/api/v1/users/" \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "password": "password123", "username": "testuser"}'
```

### 로그인 및 토큰 발급

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"username": "testuser", "password": "password123"}'
```

### 인증된 요청

```bash
curl -X GET "http://localhost:8000/api/v1/users/" \
     -H "Authorization: Bearer {access_token}"
```

## DB 필수 포함

시스템이 올바르게 작동하려면 MySQL 데이터베이스가 필요합니다. docker-compose_db.yml 설정에 포함되어 있습니다.
