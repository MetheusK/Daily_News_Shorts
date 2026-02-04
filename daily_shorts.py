import os
import feedparser
import google.generativeai as genai
import time
import socket
from datetime import datetime, timedelta
from time import mktime
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# 네트워크 타임아웃 60초
socket.setdefaulttimeout(60)

# ==========================================
# [설정] 모델 이름
MODEL_NAME = 'gemini-2.5-flash' 
# ==========================================

# 환경 변수 로드
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("🚨 경고: GEMINI_API_KEY가 환경변수에 없습니다.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

def get_gemini_response(prompt_text):
    """Gemini API 호출 함수"""
    try:
        model = genai.GenerativeModel(MODEL_NAME)
    except:
        model = genai.GenerativeModel('gemini-2.5-flash-lite')

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    try:
        response = model.generate_content(prompt_text, safety_settings=safety_settings)
        return response.text
    except Exception as e:
        return f"ERROR: {str(e)}"

def fetch_rss_feed(url, limit=3, days=1):
    """RSS 피드에서 뉴스 가져오기"""
    feed = feedparser.parse(url)
    news_items = []
    
    now = datetime.now()
    cutoff_date = now - timedelta(days=days)
    
    print(f"🔍 Searching News (Limit: {limit}, Since: {cutoff_date.strftime('%Y-%m-%d')})...")

    count = 0
    for entry in feed.entries:
        if count >= limit:
            break
            
        if hasattr(entry, 'published_parsed'):
            pub_date = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_date < cutoff_date:
                continue
        
        news_items.append(f"- Title: {entry.title}\n- Link: {entry.link}")
        count += 1
        
    return "\n\n".join(news_items)

def generate_english_shorts_script(news_data, topic_keyword):
    """
    뉴스 데이터를 바탕으로 영어 쇼츠 대본 생성
    """
    prompt = f"""
    Role: You are a professional Tech News YouTuber with 1M subscribers.
    Task: Create a **60-second YouTube Shorts script** in **ENGLISH** based on the news below.
    Topic: {topic_keyword}

    [TODAY'S NEWS]
    {news_data}

    [SCRIPT REQUIREMENTS]
    1. **Language**: 100% Natural, Native English.
    2. **Structure**:
       - **Hook (0-5s)**: Grab attention immediately.
       - **Body (5-50s)**: Summarize key points.
       - **Outro (50-60s)**: Insight + Call to Action.
    3. **Tone**: Energetic, Fast-paced.
    4. **Formatting**: Use [Visual Note] and (Narration).
    """
    return get_gemini_response(prompt)

if __name__ == "__main__":
    # =================================================
    # [설정] 주제별 검색어 및 파일명 키워드 정의
    # 나중에 여기만 바꾸면 다른 주제도 가능!
    TOPIC_KEYWORD = "semicon" # 파일명에 들어갈 짧은 키워드 (예: semicon, ai, ev)
    SEARCH_QUERY = "semiconductor+industry+AI+chip+market+trend"
    # =================================================

    rss_url = f"https://news.google.com/rss/search?q={SEARCH_QUERY}+when:1d&hl=en-US&gl=US&ceid=US:en"
    
    print(f"📰 Fetching News for Topic: {TOPIC_KEYWORD}...")
    
    news_content = fetch_rss_feed(rss_url, limit=3, days=1)
    
    if news_content:
        print("✅ News Fetched. Generating Script...")
        
        script = generate_english_shorts_script(news_content, TOPIC_KEYWORD)
        
        print("\n🎬 Generated Shorts Script:\n")
        print(script)
        
        # [수정됨] 파일명 포맷: YYMMDD_주제_script.txt
        today_str = datetime.now().strftime("%y%m%d") # 240206 형태로 변환
        filename = f"scripts/{today_str}_{TOPIC_KEYWORD}_script.txt"
        
        os.makedirs("scripts", exist_ok=True)
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(script)
        print(f"\n📂 Script saved to: {filename}")
        
    else:
        print("⚠️ No recent news found.")
