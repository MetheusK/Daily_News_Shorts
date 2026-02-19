import os
import json
import feedparser
import json
import feedparser
import google.generativeai as genai
import time
from dotenv import load_dotenv # [NEW] Local .env support

# Load environment variables from .env file (for local testing)
# User requested specific path: C:\Coding\Python
load_dotenv(r"C:\Coding\Python\.env")
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
        print(f"❌ Gemini API Error: {e}")
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

def generate_english_shorts_script(news_data, topic_keyword, mode="General_IT"):
    """
    뉴스 데이터를 바탕으로 영어 쇼츠 대본 생성 (Dual Mode)
    """
    
    # ---------------------------------------------------------
    # [모드별 프롬프트 설정]
    # ---------------------------------------------------------
    if mode == "Semicon":
        system_role = 'You are a **"Semiconductor Industry Analyst"**.'
        tone_instruction = """
        - **Focus**: Business, Stock Market, Manufacturing Yields, Supply Chain.
        - **Target**: Investors, Engineers, Industry Insiders.
        - **Tone**: Serious, Insightful, Data-driven. NO "Wow!" or "Amazing!"
        - **Keywords**: Wafer, CAPEX, Yield, HBM, GPU, Valuation.
        """
        hook_instruction = 'Hook must appeal to **Investors and Engineers** (e.g., "Stock Alert", "Yield Shock", "Market Crash").'
        
    else: # General_IT
        system_role = 'You are a **"Viral Tech Trend Hunter"**.'
        tone_instruction = """
        - **Focus**: User Experience, New Features, "Wow" Factor, Daily Life Impact.
        - **Target**: General Public, Students, Early Adopters.
        - **Tone**: Energetic, Fast-paced, Excited.
        - **Constraint**: **DO NOT** mention complex specs or manufacturing processes unless necessary.
        """
        hook_instruction = 'Hook must appeal to **General Public** (e.g., "Your phone just changed", "AI is scary", "Must Watch").'

    prompt = f"""
    Role: {system_role}
    Task: Create a Script & Visual Plan for a YouTube Short based on the news below.

    Topic: {topic_keyword}
    Mode: {mode}

    [TONE & STYLE]
    {tone_instruction}

    [HOOK STRATEGY]
    {hook_instruction}

    [CRITICAL RULE: THE HYBRID STRUCTURE]
    You must follow this exact tonal shift:

    **1. THE HOOK (0s - 3s)**
    - **Persona**: Viral Alarmist (aligned with Mode).
    - **Goal**: Stop the scroll immediately.
    - **Audio**: "Stop-the-Scroll" narration (Aggressive/Urgent).

    **2. THE BODY (3s - 60s)**
    - **Persona**: {system_role}
    - **Goal**: Retain the viewer with high-density value.
    - **Tone**: **CALM, FACTUAL, ANALYTICAL.**
    - **Instruction**: "Immediately drop the sensationalism. Do not use 'clickbait' language here. Focus purely on what happened, the numbers, and the heavy implications."
    - **CRITICAL**: DO NOT add a 'Conclusion' or 'Outro' segment. The script must end abruptly after the last data point. The system will handle the outro.
    - **Visuals**: Concrete, technical, clear.
    - **LENGTH RULE**: The body MUST contain **5-6 Segments**.
    - **WORD COUNT**: Each segment must be **20-25 WORDS**. Total script must be around **130-150 words**.
    - **DENSITY RULE**: "High Information Density" means **Numbers/Names/Dates**. Explain the "Why" and "How" in detail but keep it brief.
    - **ENDPOINT**: The LAST segment MUST be exactly:


    [HUMAN ELEMENT RULES - TECHNICAL & CINEMATIC]
    To avoid NSFW filters, you must follow these rules for ALL image prompts (Hook, Thumbnail, and Segments):
    1. **Eyes**: Use eyes ONLY in a technical context. Use terms like 'cybernetic', 'reflecting data', 'glowing iris', or 'through smart glasses'. NEVER use 'panicked', 'terror', 'bloody', or 'crying'.
    2. **Expressions**: Focus on 'Intense focus', 'Wonder', 'Serious thought', or 'Determination'. Avoid extreme negative emotions like screaming or terror.
    3. **Lighting**: Use 'Cinematic lighting', 'Cyberpunk neon', 'Dramatic side lighting' to make the person look like a movie character, not a real victim.
    4. **No Gore/Violence**: NO blood, NO weapons, NO dead bodies, NO physical harm. Use "digital corruption", "glitch effects", or "red warning lights" to convey danger instead.

    [VISUAL REQUIREMENT]
    - The "text_overlay" must be **HUGE**, **BOLD**, and **2-4 WORDS MAX**.
    - It must fill the screen.

    [TODAY'S NEWS]
    {news_data}

    [CORE DEFINITION: HOOK VS THUMBNAIL]
    
    **HOOK (The Video Intro)**: This is the first 1.5 - 3 seconds of the actual video file. It must be high-energy, fast-paced, and focus on keeping the viewer from scrolling.
    
    **THUMBNAIL (The Static Cover)**: This is a separate image file used for the YouTube feed/search results. It must be high-contrast, clean, and focus on getting the initial click.

    [THUMBNAIL VISUAL RULE]
    - **SUBJECT**: Prioritize **OBJECTS** over humans (e.g., Glowing Chips, Server Racks, Holographic Data, Robot Hands, Smartphones).
    - **AVOID**: Do not use generic "shocked face" humans unless absolutely necessary for the story.
    - **STYLE**: 3D Render, Cyberpunk, Hyper-realistic, 8k resolution.
    - **COMPOSITION**: Center the object, use dramatic backlighting.
    
    [HOOK NARRATION RULE]
    The narration in hook_plan must be a "Stop-the-Scroll" sentence. It should be more aggressive and emotional than the regular segments. Use words like "Warning", "Lies", "Crisis", or "Secret".

    [OUTPUT FORMAT - JSON ONLY]
    Return a valid JSON object.
    {{
      "hook_plan": {{
        "overlay_text": "Massive 2-3 word text to be shown INSIDE the video (e.g., 'STOP CODING!') - UPPERCASE ONLY",
        "narration": "A SHOCKING 1-sentence statement for audio (e.g., 'The AI bubble just popped, and your portfolio is in danger!')", 
        "image_description": "A dynamic, fast-paced image prompt for the video's start. (Action-oriented). FOLLOW HUMAN ELEMENT RULES.",
        "mood_color": "The dominant color for video overlays (red/neon_green/yellow)"
      }},
      "thumbnail_plan": {{
        "thumbnail_text": "2-3 word punchy text for the STATIC thumbnail (e.g., 'AI IS DEAD?') - UPPERCASE ONLY",
        "image_description": "A clean, high-contrast, cinematic background for the static cover. (Clear & Sharp). FOLLOW HUMAN ELEMENT RULES.",
        "reasoning": "Explain why this thumbnail will get clicks vs the hook."
      }},
      "title": "The Shorts Title",
      "segments": [ ... (Same as before) ... ]
    }}
    
    Example:
    {{
      "hook_plan": {{
        "overlay_text": "YOUR PHONE IS SPYING",
        "narration": "Stop what you are doing! Your phone is secretly recording everything you say.",
        "image_description": "Extreme close-up of a camera lens reflecting a scared eye, digital glitch effects, red warning lights",
        "mood_color": "red"
      }},
      "thumbnail_plan": {{
        "thumbnail_text": "DELETE THIS APP",
        "image_description": "A hand holding a smartphone with a red 'X' on the screen, dark background, cinematic lighting",
        "reasoning": "Direct command + Mystery creates high CTR."
      }},
      "title": "Smartphone Privacy Alert",
      "segments": [
        {{"text": "A new report shows that 90% of apps track your location.", "image_prompt": "Digital map of city with tracking dots...", "camera_effect": "static"}},
        ...
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
        
        # [User Request] Deduplicate and Force Static Outro
        if "segments" in result:
            # 1. Remove any LLM-generated segments that look like an outro
            result["segments"] = [
                s for s in result["segments"] 
                if "subscribe" not in s.get("text", "").lower() 
                and "subscribe" not in s.get("keyword", "").lower()
            ]
            
            # 2. Append the ONE true static outro
            result["segments"].append({
                "text": "If useful, please like and subscribe!", 
                "image_prompt": "Subscribe", # Triggers static image in make_video.py
                "keyword": "Subscribe"       # Triggers static image in make_video.py
            })
            
        return result
    except Exception as e:
        print(f"❌ JSON Parsing Error: {e}")
        print(f"📜 Raw Response Text:\n{response_text}") # Debugging info
        return None

def get_topic_by_time():
    """시간대에 따라 주제와 모드를 결정하는 함수"""
    current_hour = datetime.utcnow().hour
    
    # CASE 1: UTC 22시 ~ 00시 (KST 07시 ~ 09시 / EST 17시 ~ 19시)
    # [Semicon Mode] - 미국 장 마감 직후/한국 출근 시간
    if current_hour >= 22 or current_hour == 0:
        print(f"⏰ Current UTC: {current_hour}h -> [MODE: SEMICON Analyst] Activated")
        return {
            "keyword": "semicon",
            "search_query": "semiconductor+industry+AI+chip+market+trend+nvidia+tsmc+samsung",
            "mode": "Semicon"
        }
        
    # CASE 2: UTC 01시 ~ 03시 (KST 10시 ~ 12시 / EST 20시 ~ 22시)
    # [General IT Mode] - 미국 취침 전/한국 점심 시간
    else:
        print(f"⏰ Current UTC: {current_hour}h -> [MODE: IT TREND Hunter] Activated")
        return {
            "keyword": "tech",
            "search_query": "latest+tech+news+iphone+ai+tesla+google+gadgets",
            "mode": "General_IT"
        }

if __name__ == "__main__":
    # =================================================
    # [설정] 시간 기반 자동 실행
    # =================================================
    
    # 1. Get Config based on Time
    target_config = get_topic_by_time()
    
    TOPIC_KEYWORD = target_config["keyword"]
    SEARCH_QUERY = target_config["search_query"]
    MODE = target_config["mode"]

    rss_url = f"https://news.google.com/rss/search?q={SEARCH_QUERY}+when:1d&hl=en-US&gl=US&ceid=US:en"
    
    print(f"📰 Fetching News for Topic: {TOPIC_KEYWORD} (Mode: {MODE})...")
    
    news_content = fetch_rss_feed(rss_url, limit=3, days=1)
    
    # [Fallback Logic] If 'tech' yields no results, try 'IT'
    if not news_content and TOPIC_KEYWORD == "tech":
        print("⚠️ No news found for 'tech'. Retrying with keyword 'IT'...")
        TOPIC_KEYWORD = "IT"
        SEARCH_QUERY = "IT+industry+news+technology+trends"
        rss_url = f"https://news.google.com/rss/search?q={SEARCH_QUERY}+when:1d&hl=en-US&gl=US&ceid=US:en"
        news_content = fetch_rss_feed(rss_url, limit=3, days=1)

    if news_content:
        print(f"✅ News Fetched. Generating Script for {MODE}...")
        
        script_data = generate_english_shorts_script(news_content, TOPIC_KEYWORD, mode=MODE)
        
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
                        
                        video_title = f"{script_data.get('title', 'Daily News')} {today_str} #{TOPIC_KEYWORD}"
                        video_description = f"Daily news update about {TOPIC_KEYWORD}.\n\nSource: Google News\nGenerated by AI."
                        
                        upload_video(generated_video_path, video_title, video_description)
                        
                        # [User Request] Cleanup after upload
                        print(f"🗑️ Deleting uploaded video: {generated_video_path}")
                        # os.remove(generated_video_path)
                        
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