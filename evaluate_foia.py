import os
import json
from dotenv import load_dotenv

# Load environment variables (like OPENAI_API_KEY and CONSULAR_CACHE_DIR)
load_dotenv()

# We only import OpenAI if the key exists to avoid the immediate initialization error
api_key = os.environ.get("OPENAI_API_KEY")
if api_key:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
else:
    client = None

CACHE_DIR = os.environ.get("CONSULAR_CACHE_DIR", os.path.expanduser("~/.cache/consular"))
CACHE_FILE = os.path.join(CACHE_DIR, "atlanta_notices.json")

def load_sample_posts(limit=20):
    if not os.path.exists(CACHE_FILE):
        print(f"Cache file not found at {CACHE_FILE}. Please run scraper.py first.")
        return []

    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print("Failed to parse cache JSON.")
            return []

    # Convert dict to a list of posts and return a sample
    posts = list(data.values())
    return posts[:limit]

def evaluate_post_for_foia(title, content):
    """
    Sends the post to OpenAI to determine if it's a good candidate for an Information Disclosure Request (정보공개청구).
    """
    if not client:
        return "LLM 클라이언트가 초기화되지 않았습니다. API 키를 확인해주세요."

    prompt = f"""
    당신은 대한민국 공공기관(특히 재외공관)을 상대로 '정보공개청구(Information Disclosure Request)' 전략을 기획하는 전문가입니다.

    목적: 상대방이 비공개(영업비밀, 개인정보 등)를 핑계로 빠져나가지 못하도록, 가장 건조하고 거절할 수 없는 객관적 자료(행정 기록, 문서, 엑셀, 통계, 예산내역, 회의록 등)를 요구하여 상대방의 '공식적인 팩트(Fact)'를 강제로 고정시키는 것입니다.

    아래 공지사항을 읽고, 이 공지사항과 관련하여 우리가 정보공개청구를 통해 유의미한 '건조한 사실 데이터'를 뽑아낼 여지가 있는지 평가해주세요.

    판단 기준:
    1. 예산이 수반되는 행사나 사업인가? (예산 집행 내역, 영수증, 계약서 요구 가능)
    2. 새로운 정책이나 규정 변화인가? (관련 내부 지침, 회의록, 기안문 요구 가능)
    3. 단순 정보 전달(예: 휴무일 안내, 단순 주의사항)인가? (이런 경우는 청구 가치가 낮음)

    공지 제목: {title}
    공지 내용: {content}

    다음과 같은 형식으로 답변해주세요:

    - 추천 여부: [높음 / 중간 / 낮음]
    - 이유: (왜 청구 가치가 있는지, 혹은 없는지 당신의 추론을 2~3문장으로 설명)
    - 청구해볼 만한 구체적 자료 예시: (추천 여부가 '높음'이나 '중간'일 경우, 어떤 서류나 기록을 요구하면 거절할 수 없을지 1~2개 제안. '낮음'일 경우 "없음")
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2, # Low temperature for more analytical and consistent reasoning
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"LLM 오류: {e}"

def run_evaluation():
    posts = load_sample_posts(limit=20)

    if not posts:
        return

    print(f"--- {len(posts)}개의 공지사항 샘플에 대해 정보공개청구 가치 평가를 시작합니다 ---\n")

    for i, post in enumerate(posts, 1):
        title = post.get("title", "제목 없음")
        content = post.get("content", "")

        print(f"[{i}/{len(posts)}] 공지 제목: {title}")

        if not client:
            print("  -> 평가 건너뜀 (OPENAI_API_KEY가 설정되지 않았습니다.)\n")
            continue

        print("  -> LLM 평가 중...")
        result = evaluate_post_for_foia(title, content)
        print("  --- 평가 결과 ---")
        print(f"  {result}")
        print("  -----------------\n")

if __name__ == "__main__":
    run_evaluation()
