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
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips, vfx, ColorClip, ImageClip, CompositeAudioClip, afx
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
CLOUDFLARE_API_KEY = os.environ.get("CLOUDFLARE_API_KEY") or os.environ.get("CLOUDFLARE_API_TOKEN")

VOICE_NAME = "en-US-ChristopherNeural" # options: en-US-AriaNeural, en-US-GuyNeural
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920 # [User Request] Revert to 9:16 Vertical Ratio (Mobile)
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

    def fetch_cloudflare_image(self, query, segment_id, width=1024, height=1024):
        """
        Fetches an AI-generated image from Cloudflare Workers AI (Direct API).
        Model: @cf/black-forest-labs/flux-1-schnell
        """
        output_filename = os.path.join(self.output_dir, f"image_{segment_id}.jpg")
        
        if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_KEY or "your-account-id" in CLOUDFLARE_ACCOUNT_ID:
            print(f"      ⚠️ Cloudflare credentials not set (ID={bool(CLOUDFLARE_ACCOUNT_ID)}, Key={bool(CLOUDFLARE_API_KEY)}). Skipping.")
            return None

        # Build API URL
        # Docs: https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/
        API_URL = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell"

        # Enhanced Prompt
        enhanced_query = f"{query}, high quality, detailed, realistic, cinematic lighting"
        
        headers = {
            "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "prompt": enhanced_query,
            "width": width,   # [NEW] Dynamic Width
            "height": height, # [NEW] Dynamic Height
            "num_steps": 4    # Schnell is fast (4-8 steps)
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

    def fetch_image_from_providers(self, query, segment_id, width=1024, height=1024):
        """
        Tries to fetch image from providers in order:
        1. Cloudflare (Fastest, Free if set up)
        2. Hugging Face (High Quality, Rate Limits)
        3. Pollinations (Backup)
        4. Random Background (Last Resort)
        """
        # 1. Cloudflare
        image_path = self.fetch_cloudflare_image(query, segment_id, width, height)
        if image_path: return image_path
        
        # 2. Hugging Face
        image_path = self.fetch_hf_image(query, segment_id, width, height)
        if image_path: return image_path
        
        # 3. Pollinations
        return self.fetch_hf_image(query, segment_id, width, height) # Fallback logic is inside fetch_hf_image wrapping polliniations

    def fetch_hf_image(self, query, segment_id, width=1024, height=1024):
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
            "stabilityai/stable-diffusion-xl-base-1.0", # SDXL supports custom aspect ratios better
            "runwayml/stable-diffusion-v1-5"
        ]
        
        # Enhanced Prompt
        enhanced_query = f"{query}, high quality, detailed, realistic, cinematic lighting"
        
        for model in MODELS:
            API_URL = f"https://router.huggingface.co/hf-inference/models/{model}"
            headers = {"Authorization": f"Bearer {HF_TOKEN}"}
            
            # Adjust generic params
            use_width = width
            use_height = height
            
            if "v1-5" in model:
                # SD 1.5 prefers 512x512
                use_width = 512
                use_height = 512
            
            payload = {
                "inputs": enhanced_query,
                "parameters": {
                    "width": use_width,
                    "height": use_height,
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
        return self.fetch_pollinations_image(query, segment_id, width, height)

    def fetch_pollinations_image(self, query, segment_id, width=1024, height=1024):
        """
        Fetches an AI-generated image from Pollinations (Flux model) as a fallback.
        """
        output_filename = os.path.join(self.output_dir, f"image_{segment_id}.jpg")
        
        # Enhanced Prompt
        enhanced_query = f"{query}, high quality, detailed, realistic, cinematic lighting"
        encoded_query = requests.utils.quote(enhanced_query)
        
        # URL for Pollinations
        url = f"https://image.pollinations.ai/prompt/{encoded_query}?width={width}&height={height}&model=flux&nologo=true&seed={random.randint(0, 100000)}"
        
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



    def apply_ken_burns(self, image_path, effect_type, duration, time_offset=0):
        """
        Applies a Ken Burns effect (Zoom In/Out, Pan) to an image.
        Returns a CompositeVideoClip sized 810x1080 (matched to layout).
        time_offset: The start time of this clip relative to the start of the effect.
        """
    
    def _crop_to_aspect(self, clip_in, t_w, t_h):
        """Crops clip to match target aspect ratio (t_w/t_h) centered."""
        cur_w, cur_h = clip_in.w, clip_in.h
        target_ratio = t_w / t_h
        current_ratio = cur_w / cur_h
        
        if current_ratio > target_ratio:
            # Too wide, crop width
            new_w = cur_h * target_ratio
            return clip_in.cropped(x_center=cur_w/2, width=new_w, height=cur_h)
        else:
            # Too tall (or equal), crop height
            new_h = cur_w / target_ratio
            return clip_in.cropped(y_center=cur_h/2, width=cur_w, height=new_h)

    def apply_ken_burns(self, image_path, effect_type, duration, time_offset=0):
        try:
            # Load image
            clip = ImageClip(image_path).with_duration(duration)
            w, h = clip.w, clip.h
            
            target_w = 810 # 3:4 Image Width
            target_h = 1080 # 3:4 Image Height
            
            # Positioning in 1920px tall video
            # Center Y = 960. Top = 960 - 540 = 420.
            pos_y = 420
            
            # Normalize effect_type
            effect_type = effect_type.lower().strip() if effect_type else 'static'
            valid_effects = ['zoom_in', 'zoom_out', 'pan_right', 'pan_left']
            if effect_type not in valid_effects:
                # Static processing (Crop to 3:4)
                clip = self._crop_to_aspect(clip, target_w, target_h)
                clip = clip.resized(width=target_w)
                return clip.with_position(('center', pos_y))

            # Dynamic Processing - Rate logic
            # Let's say 0.04 per second.
            zoom_rate = 0.04
            
            if effect_type == 'zoom_in':
                # Simplified Zoom:
                # 1. Crop to target aspect ratio (3:4)
                clip = self._crop_to_aspect(clip, target_w, target_h)
                
                # 2. Resize to specific target width
                clip = clip.resized(width=target_w)
                
                # 3. Apply Zoom
                clip = clip.with_effects([vfx.Resize(lambda t: 1 + zoom_rate * (t + time_offset))])
                clip = CompositeVideoClip([clip.with_position('center')], size=(target_w, target_h))
                
            elif effect_type == 'zoom_out':
                # Same cropping logic
                clip = self._crop_to_aspect(clip, target_w, target_h)
                clip = clip.resized(width=target_w)
                
                # Zoom Out
                start_scale = 1.25
                clip = clip.with_effects([vfx.Resize(lambda t: max(1.0, start_scale - zoom_rate * (t + time_offset)))])
                clip = CompositeVideoClip([clip.with_position('center')], size=(target_w, target_h))

            elif effect_type in ['pan_right', 'pan_left']:
                # Pan horizontal
                # Resize image to height 1080
                clip = clip.resized(height=target_h)
                
                # If image is too narrow for panning, FORCE wider
                if clip.w < target_w * 1.2:
                    clip = clip.resized(width=int(target_w * 1.5))
                
                pan_speed = 50 
                
                max_x = 0
                min_x = target_w - clip.w # Negative
                
                if effect_type == 'pan_right':
                    # Image moves LEFT (Camera pans Right)
                    def pos_func_right(t):
                         curr_x = int(max(min_x, max_x - pan_speed * (t + time_offset)))
                         return (curr_x, 'center')
                    clip = clip.with_position(pos_func_right)
                    
                else: # pan_left
                    # Image moves RIGHT (Camera pans Left)
                    start_x = min_x
                    def pos_func_left(t):
                         curr_x = int(min(max_x, start_x + pan_speed * (t + time_offset)))
                         return (curr_x, 'center')
                    clip = clip.with_position(pos_func_left)
                
                clip = CompositeVideoClip([clip], size=(target_w, target_h))
            
            return clip.with_position(('center', pos_y))

        except Exception as e:
            print(f"      ⚠️ Ken Burns Error: {e}. Falling back to static.")
            # Fallback
            clip = ImageClip(image_path).with_duration(duration)
            w, h = clip.w, clip.h
            try:
                # Attempt to maintain aspect ratio crop
                 target_ratio = 810/1080
                 current_ratio = w / h
                 if current_ratio > target_ratio:
                     new_w = h * target_ratio
                     clip = clip.cropped(x_center=w/2, width=new_w, height=h)
                 else:
                     new_h = w / target_ratio
                     clip = clip.cropped(y_center=h/2, width=w, height=new_h)
                 clip = clip.resized(width=810)
            except:
                clip = clip.resized(width=810) # Crude fallback
                
            return clip.with_position(('center', pos_y))

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

    def split_text_by_words(self, text, max_chars=25):
        """
        Splits text into chunks respecting a maximum character limit,
        while strictly preserving word boundaries.
        """
        words = text.split()
        chunks = []
        current_chunk = []
        current_len = 0
        
        for w in words:
            # If adding this word exceeds limit (and we have words already), push chunk
            if current_len + len(w) > max_chars and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_len = 0
            
            current_chunk.append(w)
            current_len += len(w) + 1 # +1 for space (approx)
            
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        return chunks

    def create_karaoke_clip(self, text, duration):
        """
        Creates a karaoke-style subtitle clip where the active word is highlighted.
        Uses PIL (Pillow) to generate images directly.
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            words = text.split()
            if not words: return None
            
            # Calculate duration per word based on length
            total_chars = sum(len(w) for w in words)
            word_durations = []
            for w in words:
                if total_chars > 0:
                    d = duration * (len(w) / total_chars)
                else:
                    d = duration / len(words)
                word_durations.append(d)
                
            clips = []
            
            # Font Settings
            font_size = 70 # Slightly smaller to be safe
            try:
                # Windows standard font
                font = ImageFont.truetype("arial.ttf", font_size)
                font_bold = ImageFont.truetype("arialbd.ttf", font_size) 
            except:
                font = ImageFont.load_default()
                font_bold = font
            
            # Canvas Size
            W, H = VIDEO_WIDTH, 200
            
            start_time = 0
            
            for i, word in enumerate(words):
                # Create Image for this state
                img = Image.new('RGBA', (W, H), (0, 0, 0, 0)) 
                draw = ImageDraw.Draw(img)
                
                # [Fix] Recalculate layout for THIS state to handle Bold width correctly
                current_word_widths = []
                for j, w in enumerate(words):
                    if j == i:
                        current_word_widths.append(font_bold.getlength(w))
                    else:
                        current_word_widths.append(font.getlength(w))
                        
                space_width = font.getlength(" ") # Space is always normal font?
                total_text_width = sum(current_word_widths) + (len(words) - 1) * space_width
                
                start_x = (W - total_text_width) / 2
                y_pos = (H - font_size) / 2
                
                # Draw Loop
                curr_x = start_x
                for j, w in enumerate(words):
                    # Determine style
                    if j == i:
                        color = (255, 0, 0, 255) # Red
                        use_font = font_bold
                    else:
                        color = (255, 255, 255, 255) # White
                        use_font = font
                    
                    # Stroke effect (Black border)
                    stroke_width = 3
                    stroke_color = (0, 0, 0, 255)
                    
                    # Draw Stroke
                    for ox in range(-stroke_width, stroke_width+1):
                        for oy in range(-stroke_width, stroke_width+1):
                            if ox != 0 or oy != 0:
                                draw.text((curr_x + ox, y_pos + oy), w, font=use_font, fill=stroke_color)
                    
                    # Draw Text
                    draw.text((curr_x, y_pos), w, font=use_font, fill=color)
                    
                    # Move X based on THE WIDTH WE CALCULATED FOR THIS FRAME
                    curr_x += current_word_widths[j] + space_width
                
                # Create Clip
                import numpy as np
                img_np = np.array(img)
                txt_clip = ImageClip(img_np).with_duration(word_durations[i]).with_position(('center', 'center'))
                clips.append(txt_clip)
                
            return concatenate_videoclips(clips, method="compose")
            
        except Exception as e:
            print(f"      ⚠️ Karaoke creation failed ({e}). Falling back to static.")
            return self.create_subtitle_clip(text, duration)

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
        camera_effect = segment_data.get('camera_effect', 'static') # [NEW] Camera Effect
        time_offset = segment_data.get('time_offset', 0) # [NEW] Time Offset for continuous effect
        
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
            
            # [NEW] Determine Dimensions based on Camera Effect
            # We want the FINAL display to be 810x1080 (3:4 Ratio).
            # For Pan: Generate Wide (16:9) -> Crop/Pan inside 3:4
            # For Zoom/Static: Generate Vertical (3:4) -> exact fit
            
            if camera_effect in ['pan_right', 'pan_left']:
                # Wide 16:9 for Panning
                req_w, req_h = 1920, 1080
                if "wide" not in image_query.lower():
                    image_query += ", wide angle shot, 16:9 aspect ratio"
            else:
                # Vertical 3:4 for Zoom/Static
                # 810x1080 is the target. Let's request slightly higher res for zoom headroom?
                # Flux/SDXL likes 832x1216 or similar. 
                # Flux/SDXL likes 832x1216 or similar. 
                # Let's request 1024x1360 (Standard 3:4 High Res, divisible by 8)
                req_w, req_h = 1024, 1360 
                if "vertical" not in image_query.lower():
                    image_query += ", vertical 3:4 aspect ratio"
            
            image_path = self.fetch_image_from_providers(image_query, segment_id, req_w, req_h)
            
            # Save to cache if group_id exists
            if group_id and image_path:
                self.image_cache[group_id] = image_path
        
        # Default positioning if image fails
        image_bottom_y = 420 + 1080 
        
        if image_path and os.path.exists(image_path):
            try:
                # [NEW] Apply Ken Burns Effect with Offset
                img_clip = self.apply_ken_burns(image_path, camera_effect, duration, time_offset)
                
                # img_clip is already positioned at ('center', 250) and sized to ~900x900
                clips_to_composite.append(img_clip)
                
                # Assume height is 1080 for subtitle positioning
                image_bottom_y = 420 + 1080 
            except Exception as e:
                 print(f"      ⚠️ Image processing failed: {e}")

        # 5. Subtitle: Karaoke Style
        # Position: Middle-Bottom?
        # User said "Short 3 words", "Highlight active word", "Vertical Ratio".
        # Vertical Ratio (1080x1440) -> Middle is 720. Bottom third is around 1000.
        # Image is 900x900, pos ('center', 250). Ends at 1150.
        # So subtitle should be around 1200?
        
        # We need to make sure image fits. 
        # Layout: 
        # Header: Top 200.
        # Image: y=420, h=1080. Ends 1500.
        # Video Height: 1920.
        # Space below image: 1920 - 1500 = 420px. 
        # Plenty for subtitles (Y ~1550).
        
        sub_clip = self.create_karaoke_clip(text, duration)
        if sub_clip:
            subtitle_y = image_bottom_y + 50 # 1200
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
                
                # 2. Split Text (Karaoke Style: Max 25 chars per line)
                # User request: "Alphabet unit max"
                chunks = self.split_text_by_words(sentence, max_chars=25)
                num_chunks = len(chunks)
                chunk_duration = full_duration / num_chunks
                
                sentence_group_id = f"group_{global_segment_index}"
                sentence_clips = []
                
                
                # [Fix] Reset time offset for each new sentence group
                # Actually, chunks are sequential parts of ONE sentence.
                # So offset should accumulate.
                current_time_offset = 0 # Track time for this sentence
                
                for chunk_idx, chunk in enumerate(chunks):
                    # print(f"      🔸 Chunk {chunk_idx+1}/{num_chunks}: {chunk}")
                    
                    # Use provided image prompt
                    image_prompt = seg.get('image_prompt', keyword)
                    camera_effect = seg.get('camera_effect', 'static') # Extract here
                    
                    chunk_data = {
                        "text": chunk,
                        # "audio_path": None, # Handled globally for sentence
                        "image_prompt": image_prompt,
                        "keyword": keyword,
                        "group_id": sentence_group_id,
                        "camera_effect": camera_effect, # Pass down
                        "time_offset": current_time_offset, # Pass down
                        "total_duration": full_duration # Pass down the total duration of the sentence
                    }
                    
                    # Create visual clip (mute)
                    chunk_clip = self.process_segment(chunk_data, f"{global_segment_index}_{chunk_idx}", duration_override=chunk_duration)
                    if chunk_clip:
                        sentence_clips.append(chunk_clip)
                        
                    current_time_offset += chunk_duration # Increment offset
                
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
        
        # [NEW] Add Background Music
        bgm_path = os.path.join("assets", "Daily Shorts News BGM.mp3")
        if os.path.exists(bgm_path):
            print(f"🎵 Adding Background Music: {bgm_path}")
            try:
                bgm_clip = AudioFileClip(bgm_path)
                # Loop if video is longer than BGM
                if bgm_clip.duration < final_video.duration:
                    bgm_clip = afx.audio_loop(bgm_clip, duration=final_video.duration)
                else:
                    bgm_clip = bgm_clip.subclipped(0, final_video.duration)
                
                # Set Volume (Low so voice is clear)
                bgm_clip = bgm_clip.with_volume_scaled(0.1) # 10% volume
                
                # Mix with Voice
                final_audio = CompositeAudioClip([final_video.audio, bgm_clip])
                final_video = final_video.with_audio(final_audio)
            except Exception as e:
                print(f"⚠️ Failed to add BGM: {e}")
        
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
