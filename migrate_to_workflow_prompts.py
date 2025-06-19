# migrate_to_workflow_prompts.py - 실행 스크립트

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.database import get_db, engine, Base
from app.models import WorkflowPrompt, WorkflowPromptVersion
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 초기 프롬프트 데이터
INITIAL_PROMPTS = [
    {
        "name": "컨셉 생성 프롬프트",
        "category": "concept",
        "type": "CHAR",
        "llm_prompt": """생성형 llm을 이용해서 ai 캐릭터챗 서비스를 만들고있어. 
'페르소나' 라는 각 컨셉을 가지는 캐릭터를 생성할 예정인데, 그 전에 다양한 컨셉들을 생성하려해.
캐릭터성을 강조하고 개성을 가질 수 있는 한 두줄짜리 컨셉을 만들어줘. 

컨셉에는 캐릭터의 나이대, 성격, 직업, 성향이 잘 표현될 수 있으면 좋아.
다양한 분야와 다양한 컨셉을 가진 페르소나가 잘 나올 수 있도록 랜덤하게 생성해줘.

너무 역할극 같이 어려운 컨셉을 피해주고, 사용자가 다양한 성격의 캐릭터와 채팅을 통해 대화를 연습할 수 있는 목적이면좋아."""
    },
    {
        "name": "컨셉 생성 프롬프트",
        "category": "concept",
        "type": "STORY",
        "llm_prompt": """생성형 llm을 이용해서 ai 캐릭터챗 서비스를 만들고있어. 
'페르소나' 라는 각 컨셉을 가지는 캐릭터를 생성할 예정인데, 그 전에 다양한 컨셉들을 생성하려해.
캐릭터성을 강조하고 개성을 가질 수 있는 한 두줄짜리 컨셉을 만들어줘. 

컨셉에는 캐릭터와 사용자간의 상황이나 스토리가 나타날 수 있으면 좋아.
자극적이고 현실에서는 일어나기 어려운 상황이면 사용자의 이목을 더 끌 수 있어.
다양한 상황과 다양한 역할, 여러 예상치 못한 스토리가 나올 수 있도록 자극적이게 만들어줘. 
스토리의 주인공은 캐릭터 1명과 사용자니까 등장인물이 많이 필요한 스토리는 피해줘.

역할극 기반의 대화가 잘 이루어질 수 있는 컨셉으로 해주고 대화가 길게 이어질 수 있는 스토리면 좋아. 
분야는 로맨스, 위험한 관계, 판타지, 스릴러, 미스테리, 일상, 공포 등 상관없고 컨셉만 보고 사용자의 이목을 끌 수 있도록 자극적이면 좋아.

사용자는 남녀 가리지 않고 서비스는 성인 서비스니까 연령 제한없이 만들어줘."""
    },
    {
        "name": "페르소나 정보 생성 프롬프트",
        "category": "persona_info",
        "type": "CHAR",
        "llm_prompt": """생성형 llm을 이용해서 ai 캐릭터챗 서비스를 만들고있어. 
아래 주어진 컨셉내용을 참고해서 그 컨셉내용을 바탕으로 '페르소나'라는 캐릭터들의 정보를 생성해줘.
생성하는 페르소나 정보는 아래 '페르소나 정보 포맷'의 내용을 참고해서 맞춰서 생성해줘.

## 페르소나 컨셉내용
{concept}

## 페르소나 정보 포맷
# 프로필 정보
이름: 
성별 / 나이: 
직업: 
외형: 
말투: 
인상: 

# 배경 설정
- 페르소나에 대한 배경 설정. 캐릭터 페르소나는 사용자와의 관계가 없고 대파를 통해 소개를 받은 처음 보는 사이이므로 이 점을 참고하여 페르소나에 대한 배경 설정만 함.
- 대화 시 참고할 페르소나의 과거 배경에 대한 설명. 직업에 대한 내용이나 자라온 배경, 혹은 성격에 대한 배경 등을 작성
- 서술형태로 자유롭게 작성하나 공백포함 최대 400자를 넘지 않도록 함.

# 성격 및 말투
- 페르소나에 대한 상세한 성격과 말투에 대한 내용. MBTI를 활용하여 나타내는것이 가능하며, 성격은 가능한 구체적으로 작성함
- 말투의 경우에는 가능하면 서술형태로 설명하고 정말 필요한 경우에만 실제 예시 대사를 작성함.
- 서술형태로 자유롭게 작성하나 공백포함 최대 400자를 넘지 않도록 함.

# 성향
- 좋아하는 것과 싫어하는것, 특기, 취미 등 이 페르소나에 대한 상세한 설정을 작성해줘.
- 서술형태로 자유롭게 작성하나 공백포함 최대 200자를 넘지 않도록 함.

# 첫 대사 및 지문
- 위 페르소나의 프로필, 성격, 배경, 말투 등을 모두 참고하여 대파(만인의 친구)가 사용자에게 페르소나를 소개했다는 듯한 느낌의 대사를 작성
- () 괄호를 사용한 지문을 활용하여 현재 대화를 하는 배경이나 페르소나의 표정, 상태 등을 나타내는 것도 좋음."""
    },
    {
        "name": "페르소나 정보 생성 프롬프트",
        "category": "persona_info",
        "type": "STORY",
        "llm_prompt": """생성형 llm을 이용해서 ai 캐릭터챗 서비스를 만들고있어. 
아래 주어진 컨셉내용을 참고해서 그 컨셉내용을 바탕으로 '페르소나'라는 캐릭터들의 정보를 생성해줘.
생성하는 페르소나 정보는 아래 '페르소나 정보 포맷'의 내용을 참고해서 맞춰서 생성해줘.
## 페르소나 컨셉내용
{concept}
## 페르소나 정보 포맷
# 프로필 정보  
이름: 
성별 / 나이: 
직업: 직업 또는 신분(고등학생, 대학생 등)
외형: 
말투: 
인상: 
# 배경 설정 및 사용자와의 관계  
- 페르소나의 배경 설정내용. 구체적으로 작성하며 서술형태로 설명함.
- 사용자와의 관계에 대한 설정. 사용자가 해당 내용을 확인하여 자신의 역할을 이해할 수 있도록 작성
- 해당 내용의 마지막은 아래 '첫 대사 및 지문'에 자연스럽게 이어질 수 있도록 마무리함.
- 전체 적인 스토리 설정 상 '첫 대사 및 지문' 이전(과거) 내용에 해당
- 여백포함 약 400자 이내로 작성
# 첫 대사 및 지문  
- 괄호를 통한 지문과 일반 텍스트인 대사로 표기. 지문에서는 현재 배경과 캐릭터들의 표정이나 자세 등 필요에 따라 현재 상황을 설명.
- 대사는 페르소나의 성격과 말투를 참고하여 현재 상황에 맞도록 자연스럽게 작성. 
- 사용자와의 대화가 시작되는 순간이므로 전체적인 스토리 설정 상 사건이 시작되는 순간을 기준으로, 이목을 끌 수 있는 상황을 기준으로 설정.
- 혹은 사용자의 역할이나 정보가 필요하다면 그 내용을 질문하는 상황으로 설정.
- 가능하면 한번 정도의 대사를 포함하고 필요에 따라 두 대사 정도도 가능함.
# 대화 스토리라인  
- '첫 대사 및 지문' 항목에 이어서 이후 진행될 스토리라인.
- 배경의 전환, 사건과 이벤트 위주의 서술형태로 작성
- 대사를 포함하지 않으며 전체적인 스토리라인에서 상황의 전환이 필요한 부분에 대해서 서술.
- 페르소나는 해당 내용을 참고해서 스토리를 리드해 나감.
- 큰 단위의 사건은 3~4개를 넘지 않도록 함. 또한, 사용자의 대화방향은 예상할 수 없으므로 사용자 중심의 사건전개는 피하도록함."""
    },
    {
        "name": "요약 생성 프롬프트",
        "category": "summary",
        "type": None,
        "llm_prompt": """생성형 llm을 이용해서 ai 캐릭터챗 서비스를 만들고있어. 
아래와 같은 페르소나 속성정보가 있는데 이걸 바탕으로 서비스 상에서 보여질 '페르소나 요약'을 한줄로 작성해줘.
페르소나 요약은 30자 내외로 간결하고 임팩트 있게 작성해줘.

## 페르소나 속성정보
{personaInfo}"""
    },
    {
        "name": "태그 생성 프롬프트",
        "category": "tags",
        "type": None,
        "llm_prompt": """생성형 llm을 이용해서 ai 캐릭터챗 서비스를 만들고있어. 
아래와 같은 페르소나 속성정보가 있는데 이걸 바탕으로 서비스 상에서 보여질 '페르소나 태그'를 생성해줘.
태그는 사용자가 페르소나를 쉽게 찾고 선택할 수 있도록 도와주는 키워드들이야.

태그 생성 규칙:
- 성별, 나이대, 직업, 성격, 외모, 말투, 관심사 등을 기반으로 생성
- 한글로 작성하고, 각 태그는 2-4글자 내외로 간결하게
- 총 8-12개 정도의 태그 생성
- 아래 JSON 형태로 응답 (tags앞 여백 2칸 포함. 맨끝 콤마 포함.)
  "tags": ["외향적", "친화적", "명랑함", "따뜻함", "프리랜서", "창작직", "수다쟁이", "감성적", "활발함", "친구"],
  "sub" : ["재미", "썸남", "티키타카"],
## 페르소나 속성정보
{personaInfo}"""
    },
    {
        "name": "이미지 생성 프롬프트",
        "category": "image",
        "type": None,
        "llm_prompt": """생성형 llm을 이용해서 ai 캐릭터챗 서비스를 만들고있어. 
그 캐릭터이자 컨셉인 '페르소나'에 대해서 아래와 같은 상세 속성이 있는데 이걸 바탕으로,
서비스 상에서 보여질 페르소나의 프로필 이미지를 생성하려고해.
페르소나 정보 전달해줄테니 캐릭터성과 컨셉을 잘 이해해서 대표 이미지로 작성될 수 있도록 '이미지 프롬프트'를 '영어'로 작성해줘. 
이미지의 배경과 캐릭터의 표정, 자세 등이 컨셉에 잘 맞도록 표현됐으면 해.
기본적으로는 한국인기준이고, 컨셉에서 외국인 컨셉이라면 거기에 맞춰줘.
그리고 기본적으로 실사를 기준으로 하는데 만약 2D 애니메이션 컨셉이 더 어울린다면 네가 판단해서 2D 애니메이션으로 표현해줘.
## 페르소나 속성정보
{personaInfo}"""
    }
]

def migrate_workflow_prompts():
    """워크플로우 프롬프트로 마이그레이션 실행"""
    
    logger.info("=== 워크플로우 프롬프트 마이그레이션 시작 ===")
    
    try:
        # 1. 기존 테이블 삭제
        logger.info("1. 기존 테이블 삭제 중...")
        with engine.connect() as conn:
            # 외래키 제약조건 때문에 versions 테이블을 먼저 삭제
            conn.execute(text("DROP TABLE IF EXISTS image_prompt_versions"))
            conn.execute(text("DROP TABLE IF EXISTS persona_prompt_versions"))
            conn.execute(text("DROP TABLE IF EXISTS image_prompts"))
            conn.execute(text("DROP TABLE IF EXISTS persona_prompts"))
            conn.commit()
        logger.info("✓ 기존 테이블 삭제 완료")
        
        # 2. 새 테이블 생성
        logger.info("2. 새 테이블 생성 중...")
        Base.metadata.create_all(bind=engine)
        logger.info("✓ 새 테이블 생성 완료")
        
        # 3. 초기 데이터 삽입
        logger.info("3. 초기 프롬프트 데이터 삽입 중...")
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            for prompt_data in INITIAL_PROMPTS:
                # workflow_prompts 테이블에 삽입
                db_prompt = WorkflowPrompt(
                    name=prompt_data["name"],
                    category=prompt_data["category"],
                    type=prompt_data["type"],
                    llm_prompt=prompt_data["llm_prompt"],
                    version=1,
                    created_by=None
                )
                db.add(db_prompt)
                db.flush()  # ID 확보
                
                # workflow_prompt_versions 테이블에도 삽입
                db_version = WorkflowPromptVersion(
                    prompt_id=db_prompt.id,
                    version=1,
                    llm_prompt=prompt_data["llm_prompt"],
                    created_by=None
                )
                db.add(db_version)
                
                logger.info(f"✓ 프롬프트 추가: {prompt_data['name']}")
            
            db.commit()
            logger.info(f"✓ 총 {len(INITIAL_PROMPTS)}개 프롬프트 추가 완료")
            
        finally:
            db.close()
        
        logger.info("=== 워크플로우 프롬프트 마이그레이션 완료 ===")
        return True
        
    except Exception as e:
        logger.error(f"마이그레이션 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    success = migrate_workflow_prompts()
    if success:
        print("✅ 마이그레이션이 성공적으로 완료되었습니다!")
    else:
        print("❌ 마이그레이션 중 오류가 발생했습니다.")
        sys.exit(1)