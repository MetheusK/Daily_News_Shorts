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
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips, vfx
# from moviepy.config import change_settings
import edge_tts

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
        communicate = edge_tts.Communicate(text, VOICE_NAME)
        await communicate.save(output_file)
        return output_file

    def get_pixabay_video(self, query):
        """Fetches a stock video url from Pixabay."""
        if not PIXABAY_API_KEY:
            print("❌ PIXABAY_API_KEY not found.")
            return None

        # Pixabay Video Search
        # Docs: https://pixabay.com/api/docs/#api_search_videos
        url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={query}&per_page=3"
        
        try:
            print(f"      🔎 Searching Pixabay for: '{query}'...")
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            hits = data.get("hits", [])
            if hits:
                # Pick a random video from top 3
                video = random.choice(hits)
                # Available sizes: large, medium, small, tiny. Prefer large or medium.
                # The structure is video['videos']['large']['url']
                video_variants = video.get("videos", {})
                
                # Priority: generic large -> medium -> small
                if "large" in video_variants and video_variants["large"]["url"]:
                    return video_variants["large"]["url"]
                elif "medium" in video_variants and video_variants["medium"]["url"]:
                    return video_variants["medium"]["url"]
                elif "small" in video_variants and video_variants["small"]["url"]:
                    return video_variants["small"]["url"]
                
            print(f"      ⚠️ No videos found on Pixabay for '{query}'.")
            return None

        except Exception as e:
            print(f"      ❌ Error searching Pixabay for '{query}': {e}")
            return None

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
        """Creates a TextClip for the subtitle."""
        # Note: TextClip requires ImageMagick installed and configured.
        try:
            # Wrap text manually if needed, or rely on 'method="caption"'
            txt_clip = TextClip(
                text=text, 
                font_size=50, 
                color='white', 
                stroke_color='black', 
                stroke_width=2,
                size=(int(VIDEO_WIDTH * 0.7), int(VIDEO_HEIGHT * 0.5)), # Explicit height to prevent bottom cropping
                method='caption' 
                # align='center' 
            )
            txt_clip = txt_clip.with_position(('center', 'center')).with_duration(duration)
            return txt_clip
        except Exception as e:
            print(f"⚠️ Failed to create TextClip (ImageMagick issue?): {e}")
            return None

    def process_segment(self, segment_data, segment_id):
        """
        Processes a single segment:
        1. Load Audio
        2. Load Video (Loop/Cut)
        3. Create Subtitle
        4. Composite
        """
        text = segment_data['text']
        audio_path = segment_data['audio_path']
        video_path = segment_data['video_path']
        
        # 1. Audio
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        
        # 2. Video
        if video_path and os.path.exists(video_path):
            video_clip = VideoFileClip(video_path)
            # Loop if too short
            if video_clip.duration < duration:
                # v2: use vfx.Loop instead of loop()
                video_clip = video_clip.with_effects([vfx.Loop(duration=duration)])
            else:
                # v2: subclip -> subclipped
                video_clip = video_clip.subclipped(0, duration)
                
            # Resize/Crop to 9:16
            
            # Simple "Cover" logic
            ratio_w = VIDEO_WIDTH / video_clip.w
            ratio_h = VIDEO_HEIGHT / video_clip.h
            scale_factor = max(ratio_w, ratio_h)
            
            # v2: resize -> resized
            video_clip = video_clip.resized(scale_factor)
            video_clip = video_clip.with_position('center') 
            
            # v2: crop -> cropped
            video_clip = video_clip.cropped(width=VIDEO_WIDTH, height=VIDEO_HEIGHT, x_center=video_clip.w/2, y_center=video_clip.h/2)
            
        else:
            # Fallback black screen or color
            from moviepy import ColorClip
            video_clip = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(0,0,0)).with_duration(duration)

        video_clip = video_clip.with_audio(audio_clip)

        # 3. Subtitle
        sub_clip = self.create_subtitle_clip(text, duration)
        
        # 4. Composite
        if sub_clip:
            final_segment = CompositeVideoClip([video_clip, sub_clip], size=(VIDEO_WIDTH, VIDEO_HEIGHT))
        else:
            final_segment = video_clip
            
        return final_segment

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
                
                # Video Search (Pixabay)
                search_query = f"{keyword}"
                video_url = self.get_pixabay_video(search_query)
                if not video_url:
                     print(f"      ⚠️ Fallback to global topic: {global_topic}")
                     video_url = self.get_pixabay_video(global_topic)
                
                video_path = self.download_video(video_url, global_segment_index)
                
                segments.append({
                    "text": sentence,
                    "audio_path": audio_path,
                    "video_path": video_path
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
