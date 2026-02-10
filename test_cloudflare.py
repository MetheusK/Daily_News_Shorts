import os
import sys
from dotenv import load_dotenv

# Enhance encoding for Windows
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

# Load .env
load_dotenv(r"C:\Coding\Python\.env")

from make_video import VideoGenerator

def test_cloudflare():
    print("🧪 Testing Cloudflare Image Generation (Direct API)...")
    
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    api_key = os.environ.get("CLOUDFLARE_API_KEY") or os.environ.get("CLOUDFLARE_API_TOKEN")
    
    print(f"   Account ID: {account_id}")
    print(f"   Key: {'*' * 5} (Hidden)" if api_key else "   Key: Not Set")

    if not account_id or not api_key or "your-account-id" in account_id:
        print("❌ Cloudflare credentials are still placeholders. Please update .env.")
        return

    generator = VideoGenerator(output_dir="test_assets")
    
    prompt = "A futuristic city with flying cars, cyberpunk style, cinematic lighting"
    print(f"   Prompt: {prompt}")
    
    image_path = generator.fetch_cloudflare_image(prompt, "test")
    
    if image_path and os.path.exists(image_path):
        print(f"✅ Success! Image saved to: {image_path}")
    else:
        print("❌ Failed to generate image via Cloudflare.")

if __name__ == "__main__":
    test_cloudflare()
