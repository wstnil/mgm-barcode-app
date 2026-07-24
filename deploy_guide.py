#!/usr/bin/env python3
"""
MGM Barcode Generator — Streamlit Cloud Deployment Guide
=========================================================

Two ways to deploy your Streamlit app for free on Streamlit Community Cloud.

METHOD 1: Streamlit Community Cloud (Recommended — Free & Always Online)
-------------------------------------------------------------------------

Step 1: Go to https://share.streamlit.io/
Step 2: Sign in with your GitHub account (wstnil)
Step 3: Click "New app"
Step 4: Fill in:
  - Repository: wstnil/mgm-barcode-app
  - Branch: main
  - Main file path: barcode_streamlit.py
Step 5: Click "Deploy!"
Step 6: Wait ~2 minutes — your app will be live at:
  https://wstnil-mgm-barcode-app-barcode-streamlit.streamlit.app/

Step 7: Add secrets (for Git sync):
  - In the app dashboard, click "Settings" → "Secrets"
  - Paste:
    [github]
    pat_token = "YOUR_PAT_TOKEN_HERE"
  - Click "Save"

That's it! Your MGM Barcode Generator is now a live web app.


METHOD 2: Run Locally (For Development / Testing)
---------------------------------------------------

Step 1: Clone the repo
  git clone https://github.com/wstnil/mgm-barcode-app.git
  cd mgm-barcode-app

Step 2: Install dependencies
  pip install -r requirements.txt

Step 3: Run Streamlit
  streamlit run barcode_streamlit.py

Step 4: Open browser at http://localhost:8501


IMPORTANT NOTES
---------------

1. PAT TOKEN SECURITY:
   - NEVER put your PAT token directly in Python code
   - Use Streamlit secrets (.streamlit/secrets.toml) which are encrypted
   - On Streamlit Cloud, add secrets via the dashboard Settings → Secrets
   - The .streamlit/secrets.toml file is in .gitignore for safety
   
2. GIT SYNC:
   - The tracker file (barcode_tracker.json) lives in your GitHub repo
   - Pull before generating → Push after generating
   - This ensures uniqueness across all machines/days/months
   
3. STREAMLIT CLOUD LIMITATIONS:
   - File uploads are temporary (lost when app restarts)
   - Generated PDFs are saved to the server's temp directory
   - Download the barcode_mapping.csv from the app page immediately
   - For persistent storage, use the Git tracker sync

4. CUSTOM DOMAIN:
   - Streamlit Cloud provides a free subdomain
   - For a custom domain (e.g., mgm-barcode.mgmuniversity.ac.in),
     contact Streamlit support or use a reverse proxy
"""

print(__doc__)
