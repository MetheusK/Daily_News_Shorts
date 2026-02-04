import os
import json
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
        
        # Try to find a summary or description
        content_snippet = ""
        if hasattr(entry, 'summary'):
            content_snippet = entry.summary
        elif hasattr(entry, 'description'):
            content_snippet = entry.description
            
        # Basic HTML tag removal
        import re
        clean_content = re.sub('<[^<]+?>', '', content_snippet).strip()
        
        news_items.append(f"- Title: {entry.title}\n- Content: {clean_content}\n- Link: {entry.link}")
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

    [CONSTRAINTS]
    1. **NO FILLER**: **ABSOLUTELY NO** generic intros ("Welcome back", "Today we talk about") or outros ("Subscribe", "Thanks for watching"). 
       - **START DIRECTLY** with the first news item.
       - **END IMMEDIATELY** after the last fact.
    2. **High Density**: Focus purely on FACTS, NUMBERS, and IMPACT. Make it feel fast-paced and packed with info.
    3. **Total Word Count**: Target **140 - 150 WORDS**. (Maximize content for 60s).
    4. **Visual Keywords**: Must be **CONCRETE, VISUAL NOUNS** that exist in stock footage libraries (Pexels).
       - BAD: "future of ai", "market trend", "complex algorithm"
       - GOOD: "robot arm", "server room", "crowded street", "using smartphone", "microchip under microscope"

    [TODAY'S NEWS]
    {news_data}

    [OUTPUT FORMAT]
    Return a valid JSON object with a "title" and a list of "segments".
    Each segment must have:
    - "text": The narration sentence (Clean English, no scene directions).
    - "keyword": A single, concrete English search term for Pexels video background.
    
    Example:
    {{
      "title": "AI News Daily",
      "segments": [
        {{"text": "Nvidia's new chip creates 3D worlds in milliseconds.", "keyword": "computer chip"}},
        {{"text": "OpenAI just released a tool that clones voices instantly.", "keyword": "sound wave"}}
      ]
    }}
    """
    response_text = get_gemini_response(prompt)
    
    # JSON helper (remove markdown code blocks if present)
    import re
    import json
    try:
        json_text = re.sub(r'```json\s*|\s*```', '', response_text).strip()
        result = json.loads(json_text)
        
        # [User Request] Add mandatory short outro
        if "segments" in result:
            result["segments"].append({
                "text": "If useful, please like and subscribe!", 
                "keyword": "youtube subscribe"
            })
            
        return result
    except Exception as e:
        print(f"❌ JSON Parsing Error: {e}")
        return None

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
        
        script_data = generate_english_shorts_script(news_content, TOPIC_KEYWORD)
        
        if script_data:
            print("\n🎬 Generated Shorts Script Data:\n")
            print(json.dumps(script_data, indent=2))
            
            # [수정됨] 파일명 포맷: YYMMDD_주제_script.txt
            # GitHub Actions (UTC) -> US EST (UTC-5) 변환
            us_now = datetime.utcnow() - timedelta(hours=5)
            today_str = us_now.strftime("%y%m%d") # 240206 형태로 변환
            filename = f"scripts/{today_str}_{TOPIC_KEYWORD}_script.json"
            
            os.makedirs("scripts", exist_ok=True)
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(script_data, f, ensure_ascii=False, indent=2)
            print(f"\n📂 Script saved to: {filename}")

            # 🚀 VIDEO GENERATION START
            try:
                from make_video import VideoGenerator
                import asyncio
                
                print("🎥 Starting Video Generation Process...")
                generator = VideoGenerator()
                asyncio.run(generator.create_shorts(script_data, TOPIC_KEYWORD))
                
                # 🚀 UPLOAD START
                generated_video_path = "final_generated_shorts.mp4"
                if os.path.exists(generated_video_path):
                    print("\n🚀 Starting Upload Process...")
                    try:
                        from upload_shorts import upload_video
                        
                        video_title = f"{script_data.get('title', 'Daily News')} #{TOPIC_KEYWORD}"
                        video_description = f"Daily news update about {TOPIC_KEYWORD}.\n\nSource: Google News\nGenerated by AI."
                        
                        upload_video(generated_video_path, video_title, video_description)
                        
                        # [User Request] Cleanup after upload
                        print(f"🗑️ Deleting uploaded video: {generated_video_path}")
                        os.remove(generated_video_path)
                        
                    except Exception as e:
                        print(f"❌ Upload Failed: {e}")
                else:
                    print("⚠️ Video file not found, skipping upload.")

            except Exception as e:
                print(f"❌ Video Generation Failed: {e}")
                print("Make sure you have valid API Keys and dependencies installed.")

        else:
            print("❌ Failed to generate script.")
        
    else:
        print("⚠️ No recent news found.")