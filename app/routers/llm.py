from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
import requests
import json
import logging
from openai import OpenAI

from app.database import get_db  # 상대 경로를 절대 경로로 변경
from app.security import get_current_active_user  # 상대 경로를 절대 경로로 변경
from app.domains.users.models import User  # User 모델만 도메인에서 import

# 로깅 설정
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/llm",
    tags=["LLM"],
)

# 요청/응답 스키마
class LLMGenerateRequest(BaseModel):
    model: str  # 'gemini-2.0-flash', 'gpt-4o'
    prompt: str
    max_tokens: Optional[int] = 1000
    temperature: Optional[float] = 0.7

class LLMGenerateResponse(BaseModel):
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    model_used: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None

# --- 주요 변경 사항 ---
# OpenRouter에서 사용하는 모델 ID를 매핑합니다.
# 이렇게 하면 API 요청 시에는 'gemini-2.0-flash' 같은 간단한 이름을 사용하고,
# 실제 호출 시에는 OpenRouter에서 요구하는 전체 ID를 사용할 수 있습니다.
OPENROUTER_MODEL_MAP = {
    "gemini-2.0-flash": "google/gemini-2.0-flash-001",
    "gpt-4o": "openai/gpt-4o", # OpenRouter를 통해 GPT를 호출할 경우
    # 다른 모델도 여기에 추가할 수 있습니다.
}


# LLM 서비스 클래스
class LLMService:
    def __init__(self):
        # API 키 설정
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        # 변수명을 더 명확하게 변경했습니다.
        self.openrouter_api_key = os.getenv("OPEN_ROUTER_API_KEY")

        # OpenAI 클라이언트 초기화 (직접 호출용)
        if self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
        else:
            self.openai_client = None
            logger.warning("OPENAI_API_KEY가 설정되지 않았습니다.")

        # OpenRouter 클라이언트 초기화
        if self.openrouter_api_key:
            self.openrouter_client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.openrouter_api_key,
            )
        else:
            self.openrouter_client = None
            logger.warning("OPEN_ROUTER_API_KEY가 설정되지 않았습니다.")

    async def generate_with_openrouter(self, model_id: str, prompt: str, max_tokens: int, temperature: float) -> Dict[str, Any]:
        """OpenRouter API 호출 (Gemini 포함)"""
        try:
            if not self.openrouter_client:
                return {
                    "success": False,
                    "error": "OpenRouter API 키가 설정되지 않았습니다."
                }
            
            # OpenRouter는 OpenAI와 동일한 형식으로 API를 호출합니다.
            response = self.openrouter_client.chat.completions.create(
                model=model_id, # OpenRouter에서 사용하는 전체 모델 ID
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                usage_info = response.usage
                
                return {
                    "success": True,
                    "content": content.strip() if content else "",
                    "model_used": model_id,
                    "usage": {
                        "prompt_tokens": usage_info.prompt_tokens if usage_info else 0,
                        "completion_tokens": usage_info.completion_tokens if usage_info else 0,
                        "total_tokens": usage_info.total_tokens if usage_info else 0
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"OpenRouter({model_id})에서 응답을 생성하지 못했습니다."
                }

        except Exception as e:
            logger.error(f"OpenRouter API 오류: {e}")
            return {
                "success": False,
                "error": f"OpenRouter API 호출 중 오류가 발생했습니다: {str(e)}"
            }

    async def generate_gpt(self, prompt: str, max_tokens: int, temperature: float) -> Dict[str, Any]:
        """GPT API 직접 호출"""
        try:
            if not self.openai_client:
                return {
                    "success": False,
                    "error": "OpenAI API 키가 설정되지 않았습니다."
                }

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )

            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                usage_info = response.usage

                return {
                    "success": True,
                    "content": content.strip() if content else "",
                    "model_used": "gpt-4o",
                    "usage": {
                        "prompt_tokens": usage_info.prompt_tokens if usage_info else 0,
                        "completion_tokens": usage_info.completion_tokens if usage_info else 0,
                        "total_tokens": usage_info.total_tokens if usage_info else 0
                    }
                }
            else:
                return {
                    "success": False,
                    "error": "GPT에서 응답을 생성하지 못했습니다."
                }

        except Exception as e:
            logger.error(f"GPT API 오류: {e}")
            return {
                "success": False,
                "error": f"GPT API 호출 중 오류가 발생했습니다: {str(e)}"
            }

    async def generate(self, model: str, prompt: str, max_tokens: int, temperature: float) -> Dict[str, Any]:
        """통합 생성 메서드"""
        # OpenRouter 모델 맵에 요청된 모델이 있는지 확인
        if model in OPENROUTER_MODEL_MAP:
            openrouter_model_id = OPENROUTER_MODEL_MAP[model]
            return await self.generate_with_openrouter(openrouter_model_id, prompt, max_tokens, temperature)
        
        # OpenRouter 모델이 아니라면 기존 방식(GPT 직접호출) 시도
        elif model.startswith("gpt"):
            return await self.generate_gpt(prompt, max_tokens, temperature)
        
        else:
            return {
                "success": False,
                "error": f"지원하지 않거나 OpenRouter에 매핑되지 않은 모델입니다: {model}"
            }


# LLM 서비스 인스턴스 (이하 코드는 변경 없음)
llm_service = LLMService()

# ... (라우터 엔드포인트 코드는 그대로 사용)
@router.post("/generate", response_model=LLMGenerateResponse)
async def generate_text(
    request: LLMGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    LLM을 사용하여 텍스트 생성
    """
    try:
        logger.info(f"LLM 생성 요청 - 모델: {request.model}, 사용자: {current_user.username}")
        
        # 프롬프트 검증
        if not request.prompt.strip():
            raise HTTPException(
                status_code=400,
                detail="프롬프트가 비어있습니다."
            )
        
        # LLM 호출
        result = await llm_service.generate(
            model=request.model,
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        
        # 결과 반환
        return LLMGenerateResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LLM 생성 중 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"텍스트 생성 중 오류가 발생했습니다: {str(e)}"
        )

@router.get("/models")
async def list_available_models(
    current_user: User = Depends(get_current_active_user)
):
    """
    사용 가능한 LLM 모델 목록 반환
    """
    models = []
    
    # API 키 존재 여부에 따라 사용 가능한 모델 결정
    if llm_service.gemini_api_key:
        models.append({
            "id": "gemini-2.0-flash",
            "name": "Google Gemini 2.0 Flash",
            "provider": "Google",
            "available": True
        })
    else:
        models.append({
            "id": "gemini-2.0-flash",
            "name": "Google Gemini 2.0 Flash",
            "provider": "Google",
            "available": False,
            "reason": "API 키가 설정되지 않음"
        })
    
    if llm_service.openai_api_key:
        models.append({
            "id": "gpt-4o",
            "name": "GPT-4o",
            "provider": "OpenAI",
            "available": True
        })
    else:
        models.append({
            "id": "gpt-4o",
            "name": "GPT-4o",
            "provider": "OpenAI",
            "available": False,
            "reason": "API 키가 설정되지 않음"
        })
    
    return {
        "models": models,
        "total": len(models),
        "available": len([m for m in models if m.get("available", False)])
    }

@router.get("/health")
async def health_check():
    """
    LLM 서비스 상태 확인
    """
    return {
        "status": "healthy",
        "gemini_available": llm_service.gemini_api_key is not None,
        "openai_available": llm_service.openai_api_key is not None,
        "timestamp": "2024-01-01T00:00:00Z"  # 실제로는 현재 시간 사용
    }