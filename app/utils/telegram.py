import os
import requests
import logging
from datetime import datetime
from typing import Optional

# 로깅 설정
logger = logging.getLogger(__name__)

# 텔레그램 설정
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ADMIN_URL = os.getenv("NEXT_PUBLIC_API_BASE_URL")

def send_user_approval_request(username: str, email: str, created_at: datetime) -> bool:
    """
    새 사용자 승인 요청을 텔레그램으로 전송
    
    Args:
        username: 사용자명
        email: 이메일
        created_at: 가입일시
        
    Returns:
        bool: 전송 성공 여부
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("텔레그램 설정이 없습니다. TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID를 확인하세요.")
        return False
    
    try:
        # 가입일시 포맷팅
        formatted_date = created_at.strftime("%Y-%m-%d %H:%M:%S")
        
        # 관리자 페이지 URL
        admin_url = f"{ADMIN_URL.rstrip('/')}/admin/users"
        
        # 메시지 작성
        message = f"""🔔 새 회원가입 승인 요청

👤 사용자명: {username}
📧 이메일: {email}
🕒 가입일시: {formatted_date}
🔗 관리자 페이지: {admin_url}

승인이 필요합니다."""
        
        # 텔레그램 API 요청
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        logger.info(f"텔레그램 알림 전송 성공: {username} ({email})")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"텔레그램 API 요청 실패: {e}")
        return False
    except Exception as e:
        logger.error(f"텔레그램 알림 전송 중 오류: {e}")
        return False

def send_user_approval_notification(username: str, email: str) -> bool:
    """
    사용자 승인 완료 알림을 텔레그램으로 전송 (선택적)
    
    Args:
        username: 사용자명
        email: 이메일
        
    Returns:
        bool: 전송 성공 여부
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    
    try:
        message = f"""✅ 사용자 승인 완료

👤 사용자명: {username}
📧 이메일: {email}
🕒 승인일시: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

사용자가 이제 로그인할 수 있습니다."""
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        logger.info(f"사용자 승인 완료 알림 전송 성공: {username} ({email})")
        return True
        
    except Exception as e:
        logger.error(f"사용자 승인 완료 알림 전송 실패: {e}")
        return False