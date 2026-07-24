#!/usr/bin/env python3
"""
Quick push helper — run this from your local machine where you have GitHub access.
Usage: python3 push_helper.py YOUR_NEW_PAT_TOKEN
"""

import sys, subprocess, os

if len(sys.argv) < 2:
    print("Usage: python3 push_helper.py <YOUR_GITHUB_PAT_TOKEN>")
    print("Create a new PAT at: https://github.com/settings/tokens/new")
    print("Required scopes: repo (full control)")
    sys.exit(1)

pat = sys.argv[1]
repo_dir = os.path.dirname(os.path.abspath(__file__))

# Set authenticated remote URL
auth_url = f"https://x-access-token:{pat}@github.com/wstnil/mgm-barcode-app.git"
subprocess.run(['git', 'remote', 'set-url', 'origin', auth_url], cwd=repo_dir)

# Push
print("Pushing to GitHub...")
result = subprocess.run(
    ['git', 'push', 'origin', 'main'],
    cwd=repo_dir,
    capture_output=True, text=True, timeout=120
)
print(result.stdout)
print(result.stderr)

# Reset URL to clean (remove PAT from config)
clean_url = "https://github.com/wstnil/mgm-barcode-app.git"
subprocess.run(['git', 'remote', 'set-url', 'origin', clean_url], cwd=repo_dir)

if result.returncode == 0:
    print("\n✅ Push successful! Now deploy on Streamlit Cloud:")
    print("   1. Go to https://streamlit.io/cloud")
    print("   2. Click 'New app'")
    print("   3. Repository: wstnil/mgm-barcode-app")
    print("   4. Branch: main")
    print("   5. Main file path: barcode_streamlit.py")
    print("   6. Click 'Deploy!'")
    print("\n   Then add your PAT token in Secrets:")
    print("   App → Settings → Secrets → paste:")
    print("   [github]")
    print("   pat_token = \"YOUR_PAT_TOKEN\"")
else:
    print("\n❌ Push failed. Make sure your PAT token is valid and has 'repo' scope.")
