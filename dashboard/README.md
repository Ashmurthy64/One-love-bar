# One Love Beach Bar — Dashboard

Web dashboard for managing the One Love Beach Bar social media auto-posting system.

## Features
- Login-protected operator dashboard
- Create, edit, delete campaign posts (Facebook, Instagram, WhatsApp)
- Manage WhatsApp broadcast contact list
- Change posting schedule (time and frequency)
- Post immediately to all platforms with one click
- Test individual platforms per post
- Background scheduler for automated posting
- Activity log tracking all actions

## Quick Start (Local)
```bash
pip install -r requirements.txt
python server.py
# Open http://localhost:5000
# Login: admin / OneLove2026!
```

## Deploy to Railway
1. Push this repo to GitHub
2. Go to railway.app and create a new project
3. Select "Deploy from GitHub repo"
4. Set environment variable: `FLASK_SECRET` = any random string
5. Railway auto-deploys from the Dockerfile

## Tech Stack
- **Backend:** Python Flask
- **Frontend:** React (single HTML file, no build step)
- **Data:** JSON files (no database needed)
- **APIs:** Meta Graph API (Facebook, Instagram, WhatsApp)
