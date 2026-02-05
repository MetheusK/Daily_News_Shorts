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

VOICE_NAME = "en-US-ChristopherNeural" # options: en-US-AriaNeural, en-US-GuyNeural
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FONT_SIZE = 70
# ImageMagick path configuration might be needed on Windows
# change_settings({"IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"})

class VideoGenerator:
    def __init__(self, output_dir="temp_assets"):
        self.output_dir = output_dir
        
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

    def fetch_pixabay_image(self, query, segment_id):
        """
        Fetches a relevant image from Pixabay.
        """
        output_filename = os.path.join(self.output_dir, f"image_{segment_id}.jpg")
        
        if not PIXABAY_API_KEY:
            print("      ⚠️ PIXABAY_API_KEY missing. Using random color.")
            return self.create_random_bg(output_filename)

        url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={query}&image_type=photo&orientation=vertical&per_page=3"
        
        try:
            print(f"      🔎 [Pixabay] Searching for: '{query}'...")
            response = requests.get(url, timeout=10)
            data = response.json()
            
            hits = data.get('hits', [])
            if hits:
                # Pick a random one from top 3
                image_data = random.choice(hits)
                image_url = image_data.get('largeImageURL') or image_data.get('webformatURL')
                
                if image_url:
                    # Download
                    img_data = requests.get(image_url).content
                    with open(output_filename, 'wb') as f:
                        f.write(img_data)
                    print(f"      ✅ [Pixabay] Image Downloaded: {output_filename}")
                    return output_filename
            
            print(f"      ⚠️ No images found for '{query}'. Fallback to random color.")
            return self.create_random_bg(output_filename)

        except Exception as e:
            print(f"      ⚠️ Pixabay Error: {e}")
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

    def process_segment(self, segment_data, segment_id):
        """
        Processes a single segment with Card News Layout:
        1. Load Audio
        2. Generate Image (Flux)
        3. Create Background (Sky Blue)
        4. Composite (Image Top, Text Bottom)
        """
        text = segment_data['text']
        audio_path = segment_data['audio_path']
        keyword = segment_data.get('keyword', 'technology')
        
        # 1. Audio
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        
        # 2. Key Element: Background (Sky Blue)
        # Color: SkyBlue (135, 206, 235)
        bg_clip = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(135, 206, 235)).with_duration(duration)
        clips_to_composite = [bg_clip]

        # 3. Header: Image Overlay on Dark Blue Background
        # Dark Blue: #003366 -> (0, 51, 102)
        header_height = 200
        header_bg = ColorClip(size=(VIDEO_WIDTH, header_height), color=(0, 51, 102)).with_duration(duration).with_position(('center', 'top'))
        
        header_img_path = os.path.join("assets", "Daily Semicon News.png")
        if os.path.exists(header_img_path):
            try:
                header_img = ImageClip(header_img_path).with_duration(duration)
                # Resize height to 50% of header height (100px) as requested
                header_img = header_img.resized(height=int(header_height * 0.5))
                header_img = header_img.with_position('center')
                
                # Composite Header
                header_combined = CompositeVideoClip([header_bg, header_img], size=(VIDEO_WIDTH, header_height)).with_position(('center', 'top'))
                clips_to_composite.append(header_combined)
            except Exception as e:
                print(f"      ⚠️ Header Image Logic Failed: {e}")
                clips_to_composite.append(header_bg)
        else:
            print(f"      ⚠️ Header Image Not Found: {header_img_path}")
            clips_to_composite.append(header_bg)

        # 4. Image: Square Crop, Centered Vertical
        image_path = self.fetch_pixabay_image(keyword, segment_id)
        
        if image_path and os.path.exists(image_path):
            img_clip = ImageClip(image_path).with_duration(duration)
            
            # Smart Crop to Square (900x900)
            img_w, img_h = img_clip.size
            min_dim = min(img_w, img_h)
            
            # [Fix] Use .cropped() (v2 naming) with manual centering
            # Avoid 'center' arg, calculate top-left (x1, y1)
            x1 = (img_w - min_dim) / 2
            y1 = (img_h - min_dim) / 2
            img_clip = img_clip.cropped(x1=x1, y1=y1, width=min_dim, height=min_dim)
            
            img_clip = img_clip.resized(width=900, height=900)
            
            # Position: Below Header (Y=200) + Padding
            img_clip = img_clip.with_position(('center', 350))
            clips_to_composite.append(img_clip)
        else:
             print(f"      ⚠️ Image missing for '{keyword}', using blank.")

        # 5. Subtitle: Bottom Area
        sub_clip = self.create_subtitle_clip(text, duration)
        if sub_clip:
            # Position Text at Bottom
            sub_clip = sub_clip.with_position(('center', 1350))
            clips_to_composite.append(sub_clip)
        
        # 5. Composite
        # Ensure we set audio
        final_clip = CompositeVideoClip(clips_to_composite).with_audio(audio_clip).with_duration(duration)
        return final_clip


    async def create_shorts(self, script_data, global_topic):
        print("🚀 Starting Shorts Generation...")
        
        # 1. Parse Script (JSON)
        # script_data expected to be {'title': '...', 'segments': [{'text': '...', 'keyword': '...'}, ...]}
        segments_data = script_data.get('segments', [])
        
        segments = []
        global_segment_index = 0
        
        for i, seg in enumerate(segments_data):
            original_text = seg['text']
            keyword = seg.get('keyword') or global_topic
            
            # [User Request] Split by period for better subtitles
            # Split by . ! ? but keep the delimiter if possible, or just split by period.
            # Simple split by period is requested.
            sentences = [s.strip() for s in original_text.split('.') if s.strip()]
            
            for sentence in sentences:
                print(f"   🔹 Processing Segment {global_segment_index+1}: '{keyword}' - {sentence[:20]}...")
                
                # Async tasks
                audio_path = await self.generate_audio_segment(sentence, global_segment_index)
                
                # [Flux/Card News Update]
                # We no longer pre-download videos. We pass the KEYWORD to process_segment.
                # process_segment will generate the Flux image.
                
                segments.append({
                    "text": sentence,
                    "audio_path": audio_path,
                    "keyword": keyword, # Pass keyword for image generation
                    # "video_path": video_path # REMOVED
                })
                global_segment_index += 1

        # 2. Assemble Video
        print("🎬 Assembling Video...")
        clips = []
        for i, seg in enumerate(segments):
            clip = self.process_segment(seg, i)
            clips.append(clip)
            
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
