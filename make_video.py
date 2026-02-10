import os
import sys
# Windows CP949 encoding fix
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

import asyncio
import requests
import random
import re
import json
import shutil
import textwrap
import io
from PIL import Image
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips, vfx, ColorClip, ImageClip
import edge_tts

# ... (Configuration section remains same)


from dotenv import load_dotenv

# Load environment variables from .env file (for local testing)
load_dotenv(r"C:\Coding\Python\.env")

# ==========================================
# [Configuration]
# ==========================================
#PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")
HF_TOKEN = os.environ.get("HF_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CLOUDFLARE_API_KEY")

VOICE_NAME = "en-US-ChristopherNeural" # options: en-US-AriaNeural, en-US-GuyNeural
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_HEIGHT = 1920
FONT_SIZE = 70
VIDEO_HEIGHT = 1920
FONT_SIZE = 70
MAX_SUBTITLE_CHARS = 120 # [User Request] Increased limit for longer subtitles
# ImageMagick path configuration might be needed on Windows
# change_settings({"IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"})

class VideoGenerator:
    def __init__(self, output_dir="temp_assets"):
        self.output_dir = output_dir
        self.image_cache = {} # Cache for reusing images across split segments
        
        # Cleanup existing assets to ensure fresh generation
        if os.path.exists(output_dir):
            import shutil
            try:
                shutil.rmtree(output_dir)
                print(f"🧹 Cleaned up existing temp directory: {output_dir}")
            except Exception as e:
                print(f"⚠️ Warning: Could not fully clean temp dir: {e}")

        os.makedirs(output_dir, exist_ok=True)

    async def generate_audio_segment(self, text, segment_id):
        """Generates audio for a single sentence and returns the filepath."""
        output_file = os.path.join(self.output_dir, f"audio_{segment_id}.mp3")
        # [User Request] Speed increased by 20%
        communicate = edge_tts.Communicate(text, VOICE_NAME, rate="+20%")
        await communicate.save(output_file)
        return output_file

    def fetch_cloudflare_image(self, query, segment_id):
        """
        Fetches an AI-generated image from Cloudflare Workers AI (Direct API).
        Model: @cf/black-forest-labs/flux-1-schnell
        """
        output_filename = os.path.join(self.output_dir, f"image_{segment_id}.jpg")
        
        if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN or "your-account-id" in CLOUDFLARE_ACCOUNT_ID:
            # print("      ⚠️ Cloudflare credentials not set. Skipping.")
            return None

        # Build API URL
        # Docs: https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/
        API_URL = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell"

        # Enhanced Prompt
        enhanced_query = f"{query}, high quality, detailed, realistic, cinematic lighting"
        
        headers = {
            "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "prompt": enhanced_query
        }

        try:
            print(f"      🎨 [Cloudflare] Generating image for: '{query}'...")
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                # The direct API returns JSON with "result": {"image": "base64..."}
                if "result" in result and "image" in result["result"]:
                    import base64
                    image_b64 = result["result"]["image"]
                    image_data = base64.b64decode(image_b64)
                    
                    with open(output_filename, 'wb') as f:
                        f.write(image_data)
                    print(f"      ✅ [Cloudflare] Image Generated: {output_filename}")
                    return output_filename
                else:
                    print(f"      ⚠️ Cloudflare Response Format Error: {result.keys()}")
                    return None
            else:
                print(f"      ⚠️ Cloudflare Error: Status {response.status_code}, {response.text}")
                return None
                
        except Exception as e:
            print(f"      ⚠️ Cloudflare Exception: {e}")
            return None

    def fetch_image_from_providers(self, query, segment_id):
        """
        Tries to fetch image from providers in order:
        1. Cloudflare (Fastest, Free if set up)
        2. Hugging Face (High Quality, Rate Limits)
        3. Pollinations (Backup)
        4. Random Background (Last Resort)
        """
        # 1. Cloudflare
        image_path = self.fetch_cloudflare_image(query, segment_id)
        if image_path: return image_path
        
        # 2. Hugging Face
        image_path = self.fetch_hf_image(query, segment_id)
        if image_path: return image_path
        
        # 3. Pollinations (fetch_hf_image already falls back to this, but let's make it explicit if HF fails completely)
        # Actually fetch_hf_image logic currently handles fallback to Pollinations internally.
        # But we can restructure slightly or just call fetch_hf_image which now acts as "HF -> Pollinations" 
        # For clarity, let's keep fetch_hf_image as is for now, but rename/refactor later if needed.
        # Since fetch_hf_image calls fetch_pollinations_image on failure, we just return whatever it gave 
        # (which might be random bg).
        
        # Wait, fetch_hf_image logic:
        # Tries HF models -> if fails, calls fetch_pollinations_image -> if fails, calls create_random_bg
        # So we just need to call fetch_hf_image here if Cloudflare fails.
        return self.fetch_hf_image(query, segment_id)

    def fetch_hf_image(self, query, segment_id):
        """
        Fetches an AI-generated image from Hugging Face Inference API (Flux model).
        """
        output_filename = os.path.join(self.output_dir, f"image_{segment_id}.jpg")
        
        if not HF_TOKEN:
            print("      ⚠️ HF_TOKEN not found. Using random background.")
            return self.create_random_bg(output_filename)

        # [User Request] Fallback Models (SDXL -> SD 1.5)
        # Using router endpoint for all to avoid 410
        MODELS = [
            "runwayml/stable-diffusion-v1-5",
            "stabilityai/stable-diffusion-xl-base-1.0"
        ]
        
        # Enhanced Prompt
        enhanced_query = f"{query}, high quality, detailed, realistic, cinematic lighting"
        
        for model in MODELS:
            API_URL = f"https://router.huggingface.co/hf-inference/models/{model}"
            headers = {"Authorization": f"Bearer {HF_TOKEN}"}
            
            payload = {
                "inputs": enhanced_query,
                "parameters": {
                    "width": 1024 if "xl" in model else 512, # SDXL supports 1024, SD1.5 512
                    "height": 1024 if "xl" in model else 512, # Square
                    "guidance_scale": 7.5,
                    "num_inference_steps": 25,
                }
            }

            try:
                print(f"      🎨 [Hugging Face] Generating image with {model}...")
                response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
                
                if response.status_code == 200:
                    with open(output_filename, 'wb') as f:
                        f.write(response.content)
                    print(f"      ✅ [Hugging Face] Image Generated ({model}): {output_filename}")
                    return output_filename
                else:
                    print(f"      ⚠️ HF Error ({model}): Status {response.status_code}, {response.text}")
                    # Continue to next model
                    
            except Exception as e:
                print(f"      ⚠️ HF Exception ({model}): {e}")
                # Continue to next model

        print("      ❌ All HF models failed. Falling back to Pollinations AI...")
        return self.fetch_pollinations_image(query, segment_id)

    def fetch_pollinations_image(self, query, segment_id):
        """
        Fetches an AI-generated image from Pollinations (Flux model) as a fallback.
        """
        output_filename = os.path.join(self.output_dir, f"image_{segment_id}.jpg")
        
        # Enhanced Prompt
        enhanced_query = f"{query}, high quality, detailed, realistic, cinematic lighting"
        encoded_query = requests.utils.quote(enhanced_query)
        
        # URL for Pollinations - Square 1080x1080 for 1:1
        url = f"https://image.pollinations.ai/prompt/{encoded_query}?width=1080&height=1080&model=flux&nologo=true&seed={random.randint(0, 100000)}"
        
        try:
            print(f"      🎨 [Pollinations] Generating image for: '{query}'...")
            response = requests.get(url, timeout=60) 
            
            if response.status_code == 200:
                with open(output_filename, 'wb') as f:
                    f.write(response.content)
                print(f"      ✅ [Pollinations] Image Generated: {output_filename}")
                return output_filename
            else:
                print(f"      ⚠️ Pollinations Error: Status {response.status_code}")
                return self.create_random_bg(output_filename)

        except Exception as e:
            print(f"      ⚠️ Pollinations Exception: {e}")
            return self.create_random_bg(output_filename)

    def create_random_bg(self, output_filename):
        # Random dark colors for text readability
        r = random.randint(10, 50)
        g = random.randint(10, 50)
        b = random.randint(30, 80)
        img = Image.new('RGB', (1080, 1920), color=(r, g, b))
        img.save(output_filename)
        return output_filename



    def download_video(self, url, segment_id):
        """Downloads video to temp file."""
        if not url: return None
        output_path = os.path.join(self.output_dir, f"video_{segment_id}.mp4")
        # if os.path.exists(output_path): return output_path # Removed to force update
        
        try:
            print(f"      ⬇️ Downloading video to {output_path}...")
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(output_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return output_path
        except Exception as e:
            print(f"❌ Error downloading video: {e}")
            return None

    def extract_keywords(self, text):
        """
        Simple keyword extractor. 
        In a real app, use an LLM or NLTK. Here we just take the longest word > 4 chars
        or the subject of the sentence.
        """
        # Cleanup
        text = re.sub(r'[^\w\s]', '', text)
        words = [w for w in text.split() if len(w) > 4 and w.lower() not in ['this', 'that', 'there', 'their', 'about', 'would', 'could']]
        if words:
            return random.choice(words) # Simple randomness
        return "technology" # Fallback

    def split_text_smartly(self, text, limit=30):
        """
        Splits text into chunks respecting the limit, preferring punctuation splits.
        """
        if len(text) <= limit:
            return [text]
        
        chunks = []
        current_chunk = ""
        words = text.split()
        
        for word in words:
            if len(current_chunk) + len(word) + 1 > limit:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = word
            else:
                if current_chunk:
                    current_chunk += " " + word
                else:
                    current_chunk = word
        
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks

    def create_subtitle_clip(self, text, duration):
        """Creates a TextClip for the subtitle with manual wrapping."""
        try:
            # [User Fix] Bigger Font + Manual Wrapping
            # Font Size 60 -> Approx 30px width per char.
            # Safe width 800px / 30px = ~26 chars.
            # We use 25 chars to be safe.
            import textwrap
            wrapped_text = textwrap.fill(text, width=25)
            
            # [Fix] Add a newline character at the end to act as "Bottom Padding".
            # This prevents characters like 'g', 'y', 'j' from being cut off at the bottom.
            wrapped_text += "\n " 
            
            # Use TextClip without fixed size to allow auto-sizing
            txt_clip = TextClip(
                text=wrapped_text, 
                font_size=60, 
                color='white', 
                stroke_color='black', 
                stroke_width=3, # Thicker stroke for visibility
                # font='Arial-Bold' # REMOVED: Caused error on Windows
            )
            
            # Center on screen
            txt_clip = txt_clip.with_position(('center', 'center')).with_duration(duration)
            return txt_clip
        except Exception as e:
            print(f"⚠️ Failed to create TextClip: {e}")
            return None

    def process_segment(self, segment_data, segment_id, duration_override=None):
        """
        process_segment with Image Caching support for split sentences.
        If duration_override is provided, use it. Otherwise use audio duration.
        """
        text = segment_data['text']
        audio_path = segment_data.get('audio_path')
        keyword = segment_data.get('keyword', 'technology')
        group_id = segment_data.get('group_id') # Identifier for shared image
        
        # 1. Duration & Audio
        if duration_override:
            duration = duration_override
            audio_clip = None # Audio handled externally
        elif audio_path:
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration
        else:
            print("⚠️ No audio path or duration override provided.")
            return None
        
        # ... (Background and Header logic remains same) ...
        
        # ... (Background and Header logic remains same) ...

        # 2. Key Element: Background (Keep Dark)
        bg_clip = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 20, 30)).with_duration(duration)
        clips_to_composite = [bg_clip]

        # 3. Header
        header_height = 200
        header_bg = ColorClip(size=(VIDEO_WIDTH, header_height), color=(0, 51, 102)).with_duration(duration).with_position(('center', 'top'))
        header_img_path = os.path.join("assets", "Daily Semicon News.png")
        if os.path.exists(header_img_path):
            try:
                header_img = ImageClip(header_img_path).with_duration(duration)
                header_img = header_img.resized(height=int(header_height * 0.5))
                header_img = header_img.with_position('center')
                header_combined = CompositeVideoClip([header_bg, header_img], size=(VIDEO_WIDTH, header_height)).with_position(('center', 'top'))
                clips_to_composite.append(header_combined)
            except:
                clips_to_composite.append(header_bg)
        else:
             clips_to_composite.append(header_bg)

        # 4. Image Logic with Cache
        image_path = None
        
        # Check Cache first
        if group_id and group_id in self.image_cache:
            image_path = self.image_cache[group_id]
            # print(f"      ♻️ Reusing image for group {group_id}")
        else:
            # Generate New
            image_query = segment_data.get('image_prompt', keyword)
            image_path = self.fetch_image_from_providers(image_query, segment_id)
            
            # Save to cache if group_id exists
            if group_id and image_path:
                self.image_cache[group_id] = image_path
        
        # Default positioning if image fails
        image_bottom_y = 250 + 900 
        
        if image_path and os.path.exists(image_path):
            try:
                img_clip = ImageClip(image_path).with_duration(duration)
                img_clip = img_clip.resized(width=900)
                if img_clip.h > 900:
                    img_clip = img_clip.cropped(y1=0, y2=900)
                img_clip = img_clip.with_position(('center', 250))
                clips_to_composite.append(img_clip)
                image_bottom_y = 250 + img_clip.h
            except Exception as e:
                 print(f"      ⚠️ Image processing failed: {e}")

        # 5. Subtitle: Bottom Area (Logic Reused)
        sub_clip = self.create_subtitle_clip(text, duration)
        if sub_clip:
            subtitle_y = image_bottom_y + 50
            sub_clip = sub_clip.with_position(('center', subtitle_y))
            clips_to_composite.append(sub_clip)
        
        final_clip = CompositeVideoClip(clips_to_composite).with_audio(audio_clip).with_duration(duration)
        return final_clip


    async def create_shorts(self, script_data, global_topic):
        print("🚀 Starting Shorts Generation...")
        
        # 1. Parse Script (JSON)
        # script_data expected to be {'title': '...', 'segments': [{'text': '...', 'keyword': '...'}, ...]}
        segments_data = script_data.get('segments', [])
        
        segments = []
        clips = [] # [User Request] Ensure clips list is initialized
        global_segment_index = 0
        
        for i, seg in enumerate(segments_data):
            original_text = seg['text']
            keyword = seg.get('keyword') or global_topic
            
            # [User Request] Split by period for better subtitles
            # Split by . ! ? but keep the delimiter if possible, or just split by period.
            # Simple split by period is requested.
            sentences = [s.strip() for s in original_text.split('.') if s.strip()]
            
            for sentence in sentences:
                print(f"   🔹 Processing Sentence {global_segment_index+1}: {sentence[:30]}...")
                
                # 1. Generate Audio for ONLY the Sentence
                audio_path = await self.generate_audio_segment(sentence, global_segment_index)
                
                # Check Duration
                if not os.path.exists(audio_path):
                    print("      ⚠️ Audio generation failed, skipping.")
                    continue
                    
                full_audio_clip = AudioFileClip(audio_path)
                full_duration = full_audio_clip.duration
                
                # 2. Split Text
                chunks = self.split_text_smartly(sentence, limit=MAX_SUBTITLE_CHARS)
                num_chunks = len(chunks)
                chunk_duration = full_duration / num_chunks
                
                sentence_group_id = f"group_{global_segment_index}"
                sentence_clips = []
                
                for chunk_idx, chunk in enumerate(chunks):
                    # print(f"      🔸 Chunk {chunk_idx+1}/{num_chunks}: {chunk}")
                    
                    # Use provided image prompt
                    image_prompt = seg.get('image_prompt', keyword)
                    
                    chunk_data = {
                        "text": chunk,
                        # "audio_path": None, # Handled globally for sentence
                        "image_prompt": image_prompt,
                        "keyword": keyword,
                        "group_id": sentence_group_id
                    }
                    
                    # Create visual clip (mute)
                    chunk_clip = self.process_segment(chunk_data, f"{global_segment_index}_{chunk_idx}", duration_override=chunk_duration)
                    if chunk_clip:
                        sentence_clips.append(chunk_clip)
                
                if sentence_clips:
                    # Concatenate visual clips
                    sentence_visual = concatenate_videoclips(sentence_clips, method="compose")
                    # Set Audio
                    sentence_final = sentence_visual.with_audio(full_audio_clip)
                    clips.append(sentence_final)
                
                global_segment_index += 1

        # 2. Assemble Video
        print("🎬 Assembling Final Video...")
        # clips list now contains fully formed sentence clips (video + audio)
        
        if not clips:
            print("❌ No clips generated!")
            return None
            
        final_video = concatenate_videoclips(clips, method="compose")
        
        output_filename = "final_generated_shorts.mp4"
        final_video.write_videofile(
            output_filename, 
            fps=24, 
            codec='libx264', 
            audio_codec='aac',
            threads=4,
            preset='medium'
        )
        
        print(f"🎉 Video Saved: {output_filename}")
        return output_filename

if __name__ == "__main__":
    # Test Payload
    test_payload = {
        "title": "Semiconductor Boom",
        "segments": [
            {"text": "The semiconductor industry is booming like never before.", "keyword": "chip factory"},
            {"text": "Artificial Intelligence is driving massive demand.", "keyword": "artificial intelligence abstract"},
            {"text": "Nvidia is seeing record profits.", "keyword": "money graph"}
        ]
    }
    test_topic = "Semiconductor"
    
    generator = VideoGenerator()
    asyncio.run(generator.create_shorts(test_payload, test_topic))
