
import asyncio
import os
import sys

# Windows CP949 encoding fix
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

from make_video import VideoGenerator

async def test_pipeline():
    print("🚀 Starting Pipeline Test with Camera Effects...")
    
    # Mock Script Data with Camera Effects
    script_data = {
        "title": "Camera Effect Test",
        "segments": [
            {
                "text": "This is a test of the zoom in effect. It should focus on details.",
                "image_prompt": "Close up of a futuristic microchip, highly detailed, 8k",
                "keyword": "chip",
                "camera_effect": "zoom_in"
            },
            {
                "text": "Now we are panning right to reveal the massive factory floor.",
                "image_prompt": "Wide angle shot of a semiconductor factory, automated robots, clean room",
                "keyword": "factory",
                "camera_effect": "pan_right"
            },
            {
                "text": "Finally, a static view of the global market chart.",
                "image_prompt": "A digital holographic chart showing upward trend, blue neon style",
                "keyword": "market",
                "camera_effect": "static"
            }
        ]
    }
    
    topic = "Test"
    
    generator = VideoGenerator(output_dir="test_pipeline_assets")
    
    # Run creation
    output_file = await generator.create_shorts(script_data, topic)
    
    if output_file and os.path.exists(output_file):
        print(f"✅ Video successfully generated: {output_file}")
    else:
        print("❌ Video generation failed.")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
