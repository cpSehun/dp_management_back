#!/usr/bin/env python3
"""
t_persona 테이블 생성 및 dp_user 권한 부여 스크립트
관리자 비밀번호만 입력하면 모든 작업을 자동으로 처리합니다.

사용법:
1. 이 스크립트를 setup_persona_table.py로 저장
2. python setup_persona_table.py 실행
3. 관리자 비밀번호 입력
"""

import pymysql
import sys
import getpass

def main():
    print("=" * 60)
    print("🚀 t_persona 테이블 생성 및 권한 부여 스크립트")
    print("=" * 60)
    
    # 관리자 계정 정보 입력
    print("\n📋 MySQL 관리자 계정 정보를 입력해주세요:")
    admin_user = input("관리자 계정명 (기본값: root): ").strip() or "root"
    admin_password = getpass.getpass("관리자 비밀번호: ")
    
    if not admin_password:
        print("❌ 비밀번호를 입력해주세요.")
        sys.exit(1)
    
    # 데이터베이스 연결 설정
    connection_config = {
        'host': 'db',
        'port': 3306,
        'user': admin_user,
        'password': admin_password,
        'database': 'dp_management_db',
        'charset': 'utf8mb4'
    }
    
    try:
        print(f"\n🔗 MySQL 서버에 연결 중... ({admin_user}@xxxx:13306)")
        connection = pymysql.connect(**connection_config)
        print("✅ 연결 성공!")
        
        with connection.cursor() as cursor:
            print("\n" + "="*50)
            print("📝 1단계: t_persona 테이블 생성")
            print("="*50)
            
            # 테이블 생성 SQL
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS `dp_management_db`.`t_persona` (
                `seq` INT AUTO_INCREMENT PRIMARY KEY COMMENT '시퀀스 (기본키)',
                `id` VARCHAR(45) NULL COMMENT '페르소나 UUID (이미지 Job ID)',
                `type` VARCHAR(20) NOT NULL DEFAULT 'CHAR' COMMENT '페르소나 타입 (CHAR: 캐릭터, STORY: 스토리)',
                `name` VARCHAR(100) NOT NULL COMMENT '페르소나 이름',
                `user_id` BIGINT NULL COMMENT '사용자 ID (자기 자신 참조)',
                `status` VARCHAR(20) NOT NULL COMMENT '상태 (ACTIVE: 활성, INACTIVE: 비활성)',
                `model_id` VARCHAR(255) NULL COMMENT '사용된 LLM 모델 ID',
                `tags` JSON NULL COMMENT '태그 배열 (JSON 형태)',
                `properties` JSON NULL COMMENT '추가 속성 정보 (JSON 형태)',
                `summary` VARCHAR(100) NULL COMMENT '페르소나 요약 (최대 100자)',
                `llm_prompt` TEXT NULL COMMENT 'LLM 프롬프트 (페르소나 정보, 첫 대사 제외)',
                `chat_opening` VARCHAR(500) NULL COMMENT '첫 대사 및 지문 (대화 부분)',
                `background` VARCHAR(1000) NULL COMMENT '배경 설정',
                `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '생성 시간',
                `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정 시간',
                INDEX `idx_id` (`id`),
                INDEX `idx_user_id` (`user_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='페르소나 정보 테이블';
            """
            
            cursor.execute(create_table_sql)
            print("✅ t_persona 테이블 생성 완료")
            
            print("\n" + "="*50)
            print("🔑 2단계: dp_user 권한 부여")
            print("="*50)
            
            # 권한 부여 SQL 목록
            grant_sqls = [
                "GRANT SELECT, INSERT, UPDATE, DELETE ON `dp_management_db`.`t_persona` TO 'dp_user'@'%'",
                "GRANT SELECT, INSERT, UPDATE, DELETE ON `dp_management_db`.`t_persona` TO 'dp_user'@'localhost'",
                "GRANT SELECT, INSERT, UPDATE, DELETE ON `dp_management_db`.`t_persona` TO 'dp_user'@'192.168.65.1'",
                "FLUSH PRIVILEGES"
            ]
            
            for i, sql in enumerate(grant_sqls, 1):
                try:
                    cursor.execute(sql)
                    if "FLUSH" in sql:
                        print(f"✅ {i}. 권한 적용 완료")
                    else:
                        host = sql.split("'")[-2]  # 호스트 추출
                        print(f"✅ {i}. dp_user@{host} 권한 부여 완료")
                except Exception as e:
                    print(f"⚠️ {i}. 권한 설정 중 경고: {e}")
            
            print("\n" + "="*50)
            print("🔍 3단계: 권한 확인")
            print("="*50)
            
            # 권한 확인
            try:
                cursor.execute("SHOW GRANTS FOR 'dp_user'@'%'")
                grants = cursor.fetchall()
                print("현재 dp_user 권한:")
                for grant in grants:
                    print(f"  📋 {grant[0]}")
            except Exception as e:
                print(f"⚠️ 권한 확인 중 오류: {e}")
            
            print("\n" + "="*50)
            print("🧪 4단계: 테이블 구조 확인")
            print("="*50)
            
            # 테이블 구조 확인
            cursor.execute("DESCRIBE `dp_management_db`.`t_persona`")
            columns = cursor.fetchall()
            print("t_persona 테이블 구조:")
            print(f"{'컬럼명':<15} {'타입':<15} {'Null':<5} {'Key':<5} {'기본값':<10} {'Extra':<15}")
            print("-" * 80)
            for col in columns:
                field, type_, null, key, default, extra = col
                print(f"{field:<15} {type_:<15} {null:<5} {key:<5} {str(default or ''):<10} {extra:<15}")
            
            # 모든 변경사항 커밋
            connection.commit()
            
            print("\n" + "="*60)
            print("🎉 모든 작업이 성공적으로 완료되었습니다!")
            print("="*60)
            print("✅ t_persona 테이블 생성 완료")
            print("✅ dp_user 권한 부여 완료")
            print("✅ 설정 적용 완료")
            print("\n💡 이제 백엔드에서 t_persona 테이블에 접근할 수 있습니다!")
            
            print("\n🔍 테스트 방법:")
            print("1. 백엔드 재시작")
            print("2. GET /api/v1/persona/test/connection 호출")
            print("3. 페르소나 생성 및 저장 테스트")
            
    except pymysql.Error as e:
        print(f"\n❌ MySQL 연결 오류: {e}")
        print("\n🔧 문제 해결 방법:")
        print("1. 관리자 계정명과 비밀번호가 올바른지 확인")
        print("2. 네트워크 연결 확인 (xxxx:13306)")
        print("3. 방화벽 설정 확인")
        print("4. MySQL 서버 상태 확인")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
        sys.exit(1)
        
    finally:
        if 'connection' in locals():
            connection.close()
            print("\n🔗 데이터베이스 연결이 안전하게 종료되었습니다.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⛔ 사용자가 작업을 중단했습니다.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 스크립트 실행 중 오류: {e}")
        sys.exit(1)