
import requests
import sys
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

urls = [
    "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Black.ttf",
    "https://github.com/google/fonts/raw/main/ofl/roboto/static/Roboto-Black.ttf",
    "https://raw.githubusercontent.com/google/fonts/main/ofl/roboto/static/Roboto-Black.ttf",
    "https://raw.githubusercontent.com/google/fonts/main/apache/roboto/static/Roboto-Black.ttf",
    "https://github.com/google/fonts/blob/main/ofl/roboto/static/Roboto-Black.ttf?raw=true",
    "https://fonts.gstatic.com/s/roboto/v30/KFOlCnqEu92Fr1MmY5fBBc4.ttf",
    "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Black.ttf"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

for url in urls:
    try:
        print(f"Testing {url}...")
        r = requests.get(url, stream=True, timeout=5, headers=headers)
        if r.status_code == 200:
            chunk = next(r.iter_content(10))
            print(f"  Result: {chunk}")
            if b'<!' not in chunk and b'<html' not in chunk:
                print(f"  ✅ SUCCESS! This looks like a binary file.")
            else:
                print(f"  ❌ HTML content detected.")
        else:
            print(f"  ❌ Status: {r.status_code}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
