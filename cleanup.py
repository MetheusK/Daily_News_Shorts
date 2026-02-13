
import os
try:
    if os.path.exists("verify_changes.py"): os.remove("verify_changes.py")
    if os.path.exists("check_whoosh.py"): os.remove("check_whoosh.py")
    print("Clean up complete")
except Exception as e:
    print(f"Cleanup failed: {e}")
