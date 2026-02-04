import os
import json
import requests
import datetime
from dotenv import load_dotenv
import google.generativeai as genai

# 환경 변수 로드
load_dotenv()

# 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
TOPIC_QUERY = "반도체 산업 삼성전자 SK하이닉스" # 검색어 (나중에 변경 가능)
NEWS_COUNT = 3 # 가져올 뉴스 개수

# Gemini 설정
genai.configure(api_key=GEMINI_API_KEY)

def fetch_latest_news(query, n=3):
    """
    Serper API를 사용하여 최근 24시간(qdr:d) 내의 뉴스를 검색합니다.
    """
    url = "https://google.serper.dev/search"
    
    # qdr:d 옵션은 '지난 24시간' 필터입니다.
    payload = json.dumps({
        "q": query,
        "tbs": "qdr:d", 
        "num": 10, # 넉넉하게 가져와서 필터링
        "gl": "kr",
        "hl": "ko"
    })
    
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        data = response.json()
        
        # organic 결과 중 뉴스성 데이터만 추리기
        results = []
        if "organic" in data:
            for item in data["organic"]:
                # 제목과 요약(snippet)만 있어도 대본 작성 가능
                results.append(f"- 제목: {item.get('title')}\n- 내용: {item.get('snippet')}\n- 링크: {item.get('link')}")
                if len(results) >= n:
                    break
        
        print(f"✅ {len(results)}개의 최신 뉴스를 가져왔습니다.")
        return "\n\n".join(results)
    
    except Exception as e:
        print(f"❌ 뉴스 검색 중 오류 발생: {e}")
        return None

def generate_shorts_script(news_content):
    """
    Gemini를 사용하여 쇼츠 대본을 작성합니다.
    """
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    today_str = datetime.datetime.now().strftime("%Y년 %m월 %d일")
    
    prompt = f"""
    Role: 당신은 100만 구독자를 보유한 IT/반도체 전문 유튜버입니다.
    Task: 아래 제공된 '오늘의 반도체 뉴스' 3가지를 바탕으로 YouTube Shorts 대본을 작성해줘.
    
    [오늘의 뉴스 데이터]
    {news_content}
    
    [대본 작성 규칙]
    1. **길이:** 사람이 말했을 때 정확히 50초~55초 분량이 되도록 작성할 것.
    2. **구조:**
       - **Hook (0-5초):** 시청자의 주의를 확 끄는 강렬한 첫 마디 (예: "오늘 반도체 시장, 이 소식 놓치면 손해입니다!")
       - **Body (5-45초):** 3가지 뉴스를 핵심만 요약해서 빠르게 전달. 어려운 용어는 쉽게 풀어설명.
       - **Outro (45-60초):** 간단한 투자 인사이트 한 줄 + "구독과 좋아요" 유도.
    3. **톤앤매너:** 빠르고, 명확하고, 에너지 넘치게. (존댓말 사용: ~습니다, ~해요)
    4. **형식:** 아래 형식을 반드시 지켜줘.
    
    ---
    (제목: 흥미로운 제목)
    
    [화면: 역동적인 반도체 관련 영상]
    (자막: 핵심 키워드)
    내레이션: "..."
    
    [화면: 첫 번째 뉴스 관련 자료화면]
    (자막: 뉴스 1 요약)
    내레이션: "..."
    
    ... (나머지 뉴스) ...
    
    [화면: 채널 로고]
    내레이션: "..."
    ---
    """
    
    response = model.generate_content(prompt)
    return response.text

def save_script_to_file(script):
    """
    대본을 txt 파일로 저장합니다.
    """
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    filename = f"scripts/script_{today_str}.txt"
    
    # 폴더가 없으면 생성
    os.makedirs("scripts", exist_ok=True)
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(script)
    
    print(f"📂 대본이 저장되었습니다: {filename}")

if __name__ == "__main__":
    print("🔍 오늘의 반도체 뉴스를 검색합니다...")
    news_data = fetch_latest_news(TOPIC_QUERY, n=NEWS_COUNT)
    
    if news_data:
        print("🤖 쇼츠 대본을 작성 중입니다...")
        script = generate_shorts_script(news_data)
        
        print("\n" + "="*50)
        print(script)
        print("="*50 + "\n")
        
        save_script_to_file(script)
    else:
        print("뉴스 데이터를 가져오지 못해 종료합니다.")