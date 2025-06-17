#!/usr/bin/env python3
"""
관리자 계정 생성 스크립트
사용법: python create_admin.py
"""
import os
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from app import models, schemas, security, crud
from app.database import SessionLocal, engine

def create_admin_user():
    """관리자 계정 생성 함수"""
    
    # 관리자 정보 설정
    ADMIN_CONFIG = {
        "username": "admin",
        "email": "admin@cplabs.io", 
        "password": "cplabs34",
        "full_name": "관리자"
    }
    
    print("=" * 50)
    print("🔧 관리자 계정 생성 스크립트")
    print("=" * 50)
    
    # 데이터베이스 연결 확인
    try:
        db = SessionLocal()
        print("✅ 데이터베이스 연결 성공")
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        return False
    
    try:
        # 기존 사용자 확인
        existing_user_by_username = crud.get_user_by_username(db, username=ADMIN_CONFIG["username"])
        existing_user_by_email = crud.get_user_by_email(db, email=ADMIN_CONFIG["email"])
        
        if existing_user_by_username:
            print(f"⚠️  사용자명 '{ADMIN_CONFIG['username']}'이 이미 존재합니다.")
            
            # 기존 사용자를 관리자로 업데이트할지 묻기
            response = input("기존 사용자를 관리자로 업데이트하시겠습니까? (y/N): ")
            if response.lower() == 'y':
                # 기존 사용자 업데이트
                existing_user_by_username.is_active = True
                existing_user_by_username.is_superuser = True
                existing_user_by_username.full_name = ADMIN_CONFIG["full_name"]
                
                # 패스워드도 업데이트할지 확인
                update_password = input("패스워드도 업데이트하시겠습니까? (y/N): ")
                if update_password.lower() == 'y':
                    existing_user_by_username.hashed_password = security.get_password_hash(ADMIN_CONFIG["password"])
                
                db.commit()
                db.refresh(existing_user_by_username)
                
                print("✅ 기존 사용자가 관리자로 업데이트되었습니다!")
                print_user_info(existing_user_by_username, ADMIN_CONFIG["password"])
                return True
            else:
                print("❌ 작업이 취소되었습니다.")
                return False
        
        if existing_user_by_email:
            print(f"⚠️  이메일 '{ADMIN_CONFIG['email']}'이 이미 존재합니다.")
            print("❌ 다른 이메일을 사용하거나 기존 사용자를 삭제해주세요.")
            return False
        
        # 새 관리자 사용자 생성
        print("🔨 새 관리자 계정을 생성합니다...")
        
        # UserCreate 스키마 사용하여 사용자 생성
        user_create = schemas.UserCreate(
            username=ADMIN_CONFIG["username"],
            email=ADMIN_CONFIG["email"],
            password=ADMIN_CONFIG["password"],
            full_name=ADMIN_CONFIG["full_name"]
        )
        
        # CRUD 함수를 통해 생성 (자동으로 패스워드 해싱됨)
        db_user = crud.create_user(db=db, user=user_create)
        
        # 관리자 권한 부여
        db_user.is_active = True
        db_user.is_superuser = True
        db.commit()
        db.refresh(db_user)
        
        print("✅ 관리자 계정이 성공적으로 생성되었습니다!")
        print_user_info(db_user, ADMIN_CONFIG["password"])
        
        return True
        
    except Exception as e:
        print(f"❌ 계정 생성 중 오류 발생: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def print_user_info(user, password):
    """사용자 정보 출력"""
    print("\n" + "=" * 30)
    print("📋 생성된 관리자 정보")
    print("=" * 30)
    print(f"ID: {user.id}")
    print(f"사용자명: {user.username}")
    print(f"이메일: {user.email}")
    print(f"이름: {user.full_name}")
    print(f"활성화: {user.is_active}")
    print(f"관리자: {user.is_superuser}")
    print(f"생성일: {user.created_at}")
    print("=" * 30)
    print("🔑 로그인 정보")
    print("=" * 30)
    print(f"사용자명: {user.username}")
    print(f"패스워드: {password}")
    print("=" * 30)

def verify_admin_login():
    """생성된 관리자 계정 로그인 테스트"""
    print("\n🔍 로그인 테스트를 진행합니다...")
    
    db = SessionLocal()
    try:
        # 로그인 테스트
        user = crud.authenticate_user(db, username="admin", password="cplabs34")
        if user:
            print("✅ 로그인 테스트 성공!")
            print(f"   - 사용자: {user.username}")
            print(f"   - 활성화: {user.is_active}")
            print(f"   - 관리자: {user.is_superuser}")
        else:
            print("❌ 로그인 테스트 실패!")
            return False
    except Exception as e:
        print(f"❌ 로그인 테스트 중 오류: {e}")
        return False
    finally:
        db.close()
    
    return True

def main():
    """메인 함수"""
    print("관리자 계정 생성을 시작합니다...\n")
    
    # 관리자 계정 생성
    if create_admin_user():
        # 로그인 테스트
        if verify_admin_login():
            print("\n🎉 모든 작업이 완료되었습니다!")
            print("\n📌 주의사항:")
            print("   1. 보안을 위해 초기 패스워드를 변경하는 것을 권장합니다.")
            print("   2. 프로덕션 환경에서는 더 강력한 패스워드를 사용하세요.")
            print("   3. 이 스크립트 실행 후 파일을 안전하게 삭제하세요.")
        else:
            print("\n⚠️  계정은 생성되었지만 로그인 테스트에 실패했습니다.")
            print("   데이터베이스를 확인해주세요.")
    else:
        print("\n❌ 관리자 계정 생성에 실패했습니다.")

if __name__ == "__main__":
    main()