#!/bin/bash
# ============================================================================
# Push script for MGM Barcode App
# Run this from your local machine where you have GitHub access:
#   cd mgm-barcode-app && bash push_to_github.sh
# Or just run: git push origin main
# ============================================================================

echo "=== MGM Barcode App — Push to GitHub ==="

# Check if we're in the right directory
if [ ! -f "barcode_streamlit.py" ]; then
    echo "ERROR: Run this from the mgm-barcode-app directory"
    exit 1
fi

# Push all commits
echo "Pushing to GitHub..."
git push origin main

echo ""
echo "=== Done! ==="
echo "Now deploy on Streamlit Cloud:"
echo "1. Go to https://streamlit.io/cloud"
echo "2. Click 'New app'"
echo "3. Select repo: wstnil/mgm-barcode-app"
echo "4. Main file path: barcode_streamlit.py"
echo "5. Click 'Deploy!'"
echo ""
echo "Add secrets in Streamlit Cloud → Settings → Secrets:"
echo '[github]'
echo 'pat_token = "YOUR_GITHUB_PAT_TOKEN_HERE"'
