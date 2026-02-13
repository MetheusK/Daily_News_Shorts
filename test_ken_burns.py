
import os
import sys
import random
import requests
import asyncio
from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, vfx
from PIL import Image
import numpy as np

# Windows CP949 encoding fix
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv

# Load environment variables
load_dotenv(r"C:\Coding\Python\.env")

# Configuration
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_KEY = os.environ.get("CLOUDFLARE_API_KEY") or os.environ.get("CLOUDFLARE_API_TOKEN")

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
OUTPUT_DIR = "ken_burns_test_assets"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_cloudflare_image(prompt, filename):
    """
    Generates an image using Cloudflare FLUX model with 'wide angle' prompt.
    """
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_KEY:
        print("⚠️ Cloudflare credentials missing. Generating placeholder.")
        return create_placeholder_image(filename)

    API_URL = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    
    # Enhanced prompt for Ken Burns (Wide Angle)
    enhanced_prompt = f"{prompt}, wide angle shot, centered composition, high resolution, 8k, cinematic lighting, lots of details"
    
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {"prompt": enhanced_prompt}

    try:
        print(f"🎨 Generating image: '{prompt}'...")
        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            if "result" in result and "image" in result["result"]:
                import base64
                image_data = base64.b64decode(result["result"]["image"])
                with open(filename, 'wb') as f:
                    f.write(image_data)
                print(f"✅ Image saved: {filename}")
                return filename
    except Exception as e:
        print(f"❌ Error generating image: {e}")

    return create_placeholder_image(filename)

def create_placeholder_image(filename):
    """Creates a random colored image if generation fails."""
    color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    img = Image.new('RGB', (1024, 1024), color)
    img.save(filename)
    print(f"⚠️ Placeholder saved: {filename}")
    return filename

from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, vfx, ColorClip, TextClip
import textwrap

# ... [Previous code remains until apply_ken_burns] ...

def create_subtitle_clip(text, duration):
    """Creates a TextClip for the subtitle with manual wrapping, matching make_video.py."""
    try:
        # Wrap text
        wrapped_text = textwrap.fill(text, width=25)
        wrapped_text += "\n " # Bottom padding
        
        txt_clip = TextClip(
            text=wrapped_text, 
            font_size=60, 
            color='white', 
            stroke_color='black', 
            stroke_width=3,
            method='caption', # Try caption method if available or default
            size=(VIDEO_WIDTH, None) # Width constrained
        )
        
        # Center on screen, but pushed down
        # In make_video.py, it's image_bottom_y + 50.
        # Here we hardcode image pos: 250 + 900 = 1150. So y=1200.
        txt_clip = txt_clip.with_position(('center', 1200)).with_duration(duration)
        return txt_clip
    except Exception as e:
        print(f"⚠️ Failed to create TextClip: {e}")
        return None

def apply_ken_burns(image_path, effect_type='zoom_in', duration=5):
    """
    Applies a Ken Burns effect (Zoom In/Out, Pan) to an image.
    Returns a VideoClip resized to 900 width for the layout.
    """
    # Load image
    clip = ImageClip(image_path).with_duration(duration)
    
    w, h = clip.w, clip.h
    
    # We want the FINAL clip to be roughly 900x900 (or similar aspect) 
    # to fit in the layout slot (y=250).
    # The layout demands: Image at y=250. Max width 900.
    
    # Internal Logic:
    # 1. Create a larger canvas for the effect (e.g. 1200x1200)
    # 2. Apply Zoom/Pan
    # 3. Resize the RESULT to fit the 900px wide slot.
    
    # Let's target a squareish aspect for simplicity or vertical?
    # User said "Shorts layout", usually 9:16 overall, but the image is a window.
    # In make_video.py: img_clip.resized(width=900).cropped(y1=0, y2=900).
    # So target final size is 900x900.
    
    target_w = 900
    target_h = 900
    
    # We need the source image to be larger than 900x900 to zoom/pan without upscaling artifacts?
    # Cloudflare Flux gives 1024x1024. That's good.
    
    if effect_type == 'zoom_in':
        # 1. Start at 900x900 center crop?
        # No, we want to zoom IN.
        # Start: Show full image (scaled to 900x900).
        # End: Show cropped area.
        
        # Or: Use vfx.Resize on the clip itself.
        # To avoid black bars during zoom, we need to ensure aspect ratio matches.
        
        # Force crop to square first
        min_dim = min(w, h)
        # crop(x_center=..., y_center=..., width=..., height=...)
        clip = clip.cropped(width=min_dim, height=min_dim, x_center=w/2, y_center=h/2)
        
        # Resize to slightly larger than 900 so we can zoom
        base_size = int(target_w * 1.0) # Start exactly at target size?
        
        # Logic: 
        # Clip is 1024x1024.
        # We want final output in layout to be 900x900.
        
        # Apply Resize effect: 1.0 -> 1.3
        # clip.resized(lambda t: 1 + 0.05*t) makes it grow.
        # We then need to Compositing it into a 900x900 box?
        # If the clip grows, and we composite it into 900x900 centered, we get a Zoom In effect.
        
        clip = clip.with_effects([vfx.Resize(lambda t: 1 + 0.06 * t)]) # Grow
        
        # Composite center 900x900
        clip = CompositeVideoClip([clip.with_position('center')], size=(target_w, target_h))

    elif effect_type == 'zoom_out':
        # Force crop square
        min_dim = min(w, h)
        clip = clip.cropped(width=min_dim, height=min_dim, x_center=w/2, y_center=h/2)

        # Start large
        clip = clip.with_effects([vfx.Resize(lambda t: 1.3 - 0.06 * t)])
        clip = CompositeVideoClip([clip.with_position('center')], size=(target_w, target_h))
        
    elif effect_type == 'pan_right':
        # Pan horizontal.
        # We need height = target_h (900).
        # Resize image to height 900.
        ratio = target_h / h
        new_w = int(w * ratio)
        clip = clip.resized(height=target_h)
        
        # Note: If new_w < 900, we have a problem (black bars).
        if clip.w < target_w:
            # Resize by width instead
            clip = clip.resized(width=int(target_w * 1.5))
        
        # Pan x: 0 to (900 - clip.w)
        # Note: clip.w is typically > 900 now.
        start_x = 0
        end_x = target_w - clip.w
        
        clip = clip.with_position(lambda t: (int(start_x + (end_x - start_x) * (t / duration)), 'center'))
        clip = CompositeVideoClip([clip], size=(target_w, target_h))

    return clip

def create_layout_clip(ken_burns_clip, subtitle_text, duration):
    """
    Wraps the Ken Burns clip into the full Shorts layout.
    """
    # 1. Background
    bg_clip = ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=(20, 20, 30)).with_duration(duration)
    
    # 2. Header
    header_height = 200
    header_bg = ColorClip(size=(VIDEO_WIDTH, header_height), color=(0, 51, 102)).with_duration(duration).with_position(('center', 'top'))
    
    # Try loading header image
    header_items = [header_bg]
    header_img_path = os.path.join("assets", "Daily Semicon News.png")
    if os.path.exists(header_img_path):
        header_img = ImageClip(header_img_path).with_duration(duration)
        header_img = header_img.resized(height=int(header_height * 0.5))
        header_img = header_img.with_position('center')
        header_items.append(header_img)
    
    header_combined = CompositeVideoClip(header_items, size=(VIDEO_WIDTH, header_height)).with_position(('center', 'top'))
    
    # 3. Ken Burns Image (Positioned at y=250)
    # ken_burns_clip is already 900x900 (or similar)
    kb_clip = ken_burns_clip.with_position(('center', 250))
    
    # 4. Subtitle
    sub_clip = create_subtitle_clip(subtitle_text, duration)
    
    layers = [bg_clip, header_combined, kb_clip]
    if sub_clip:
        layers.append(sub_clip)
        
    return CompositeVideoClip(layers, size=(VIDEO_WIDTH, VIDEO_HEIGHT)).with_duration(duration)


async def main():
    print("🚀 Starting Ken Burns Semicon Test...")
    
    # 1. Generate Images with Realistic Prompts
    # Scenario 1: Samsung 3nm Chip
    img1 = os.path.join(OUTPUT_DIR, "img_semicon_wafer.jpg")
    prompt1 = "Extreme close up of a futuristic 3nm semiconductor silicon wafer with intricate circuit patterns, glowing blue lines, cinematic lighting, highly detailed, 8k, wide angle"
    
    # Scenario 2: Automated Factory
    img2 = os.path.join(OUTPUT_DIR, "img_semicon_factory.jpg")
    prompt2 = "Futuristic semiconductor manufacturing factory interior, automated robot arms handling wafers, clean room, white and blue color scheme, wide angle shot, high resolution"
    
    if not os.path.exists(img1):
        fetch_cloudflare_image(prompt1, img1)
    
    if not os.path.exists(img2):
        fetch_cloudflare_image(prompt2, img2)
        
    # 2. Create Clips with Effects AND Layout
    print("🎬 Creating Clips...")
    
    # Clip 1: Zoom In + Layout
    # "Samsung Electronics unveils industry's first 3nm process chip."
    kb1 = apply_ken_burns(img1, effect_type='zoom_in', duration=5)
    clip1 = create_layout_clip(kb1, "Samsung Electronics unveils industry's first 3nm process chip.", 5)
    
    # Clip 2: Pan Right + Layout
    # "Global semiconductor market expected to reach $1 trillion by 2030."
    kb2 = apply_ken_burns(img2, effect_type='pan_right', duration=5)
    clip2 = create_layout_clip(kb2, "Global semiconductor market expected to reach $1 trillion by 2030.", 5)
    
    # 3. Concatenate
    final_video = concatenate_videoclips([clip1, clip2])
    
    output_file = "ken_burns_semicon_test.mp4"
    final_video.write_videofile(output_file, fps=24, threads=4)
    print(f"🎉 Test Video Saved: {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
