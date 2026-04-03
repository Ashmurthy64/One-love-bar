#!/usr/bin/env python3
"""
One Love Beach Bar — Dashboard Server
Flask backend that wraps post_agent.py and serves the web UI.
Includes DALL-E 3 AI image generation and GitHub Pages upload.

Now uses JWT authentication for cross-domain API access.
Frontend is served separately on GitHub Pages at https://ashmurthy64.github.io

Requirements:
    pip install flask flask-cors requests schedule openai pyjwt

Run:
    python server.py
    Then access the API from https://ashmurthy64.github.io
"""

import os
import json
import time
import threading
import secrets
import hashlib
import base64
import re
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests as http_requests
import jwt

# ══════════════════════════════════════════════
# APP SETUP
# ══════════════════════════════════════════════
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", secrets.token_hex(32))
JWT_SECRET = os.getenv("JWT_SECRET", app.secret_key)
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# CORS Configuration for GitHub Pages frontend
CORS(app,
     resources={r"/api/*": {
         "origins": ["https://ashmurthy64.github.io", "https://onelovebeachbar.com"],
         "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         "allow_headers": ["Content-Type", "Authorization"],
         "expose_headers": ["Content-Type"],
         "supports_credentials": True,
         "max_age": 3600
     }}
)

# ══════════════════════════════════════════════
# DATA FILES — stored as JSON alongside server.py
# ══════════════════════════════════════════════
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

CONFIG_FILE = DATA_DIR / "config.json"
POSTS_FILE = DATA_DIR / "posts.json"
RECIPIENTS_FILE = DATA_DIR / "recipients.json"
STATE_FILE = DATA_DIR / "agent_state.json"
LOGS_FILE = DATA_DIR / "post_logs.json"
USERS_FILE = DATA_DIR / "users.json"
CAMPAIGN_CONTEXT_FILE = DATA_DIR / "campaign_context.json"

# ══════════════════════════════════════════════
# DEFAULT DATA
# ══════════════════════════════════════════════
DEFAULT_CAMPAIGN_CONTEXT = {
    "brand": {
        "name": "One Love Beach Bar",
        "location": "Playa Ballenas, Las Terrenas, Samaná, Dominican Republic",
        "vibe": "Warm, tropical, inviting, authentic Caribbean energy",
        "tagline": "Good vibes, great drinks, right on the beach",
        "colors": "Warm golds, ocean blues, sunset oranges, lush greens",
        "target_audience": "Expats, tourists, digital nomads, locals who love beach culture",
        "tone_of_voice": "Friendly, laid-back, warm but not cheesy. Think 'cool friend who owns a beach bar' not 'corporate resort'",
        "hashtags_always": ["#OneLoveBeachBar", "#LasTerrenas", "#Samana", "#PlayaBallenas", "#DominicanRepublic"],
        "hashtags_optional": ["#BeachBar", "#Caribbean", "#TropicalVibes", "#BeachLife", "#IslandLife", "#CocktailBar"],
        "dos": [
            "Use warm, golden-hour lighting in images",
            "Show real beach/ocean scenery when possible",
            "Include cocktails, palm trees, sunsets as visual motifs",
            "Keep captions conversational and inviting",
            "Use emojis sparingly but effectively in FB/IG captions",
        ],
        "donts": [
            "Don't use stock photo aesthetic — keep it authentic",
            "Don't overuse neon or artificial colors",
            "Don't make it look like a chain restaurant",
            "Don't use overly salesy language",
            "Avoid cliché phrases like 'paradise found' or 'life's a beach'",
        ],
    },
    "campaign_phase": "pre-launch",
    "campaign_notes": "Currently in coming-soon / teaser phase. Building anticipation before grand opening.",
    "style_preferences": {
        "preferred_image_styles": ["tropical beach bar photography", "warm golden hour lighting", "Caribbean lifestyle"],
        "avoided_styles": ["dark moody", "urban", "corporate"],
        "preferred_compositions": ["wide beach shots", "close-up cocktails", "sunset silhouettes"],
    },
    "generation_history": [],
}

DEFAULT_CONFIG = {
    "app_id": "1669620497794638",
    "app_secret": os.getenv("META_APP_SECRET", ""),
    "page_access_token": os.getenv("PAGE_ACCESS_TOKEN", "EAAXugtCuRk4BROJpyFxoJN6uohZAe7KdCectbYHdLYhmaficZCkdiCyQXX369Vx7CBZB0cGZAY6stp2JGtvcNbWbvqWqW3TYWa42ahQOsR2gyXkJNICZAAW7vPyJaxeA3Pv3BZAFfLuOk3LLkHWzgppXOdUfkN6dqq89uMcPZCfMiMPLZAq7Fc6ZADsbONvp7NU7gmAZDZD"),
    "page_id": os.getenv("PAGE_ID", "1005826949287918"),
    "instagram_account_id": os.getenv("IG_ACCOUNT_ID", "17841439106843704"),
    "wa_phone_number_id": os.getenv("WA_PHONE_NUMBER_ID", "990492627489867"),
    "wa_business_account_id": os.getenv("WA_BUSINESS_ACCOUNT_ID", "1325691766278431"),
    "post_time": "10:00",
    "post_interval_days": 2,
    "report_recipient": os.getenv("WA_REPORT_TO", "15713410830"),
    "image_base_url": "https://ashmurthy64.github.io/One-love-bar/images/",
}

DEFAULT_POSTS = [
    {
        "id": "coming_soon",
        "caption": "Something Special Is Coming\n\nOne Love Beach Bar is almost ready to open its doors on Playa Ballenas. Tropical cocktails, warm vibes and good energy right on the beach.\n\nStay tuned — One Love is coming to Las Terrenas, Samana",
        "fb_caption": "✦ Something Special Is Coming ✦\n\nOne Love Beach Bar is almost ready to open its doors on Playa Ballenas. 🌴 Tropical cocktails, warm vibes and good energy right on the beach.\n\nStay tuned — One Love is coming to Las Terrenas, Samaná 🇩🇴🍹\n\n#OneLoveBeachBar #LasTerrenas #Samana #PlayaBallenas #ComingSoon #TropicalCocktails #DominicanRepublic #BeachBar #Caribbean",
        "image_file": "post1-coming-soon.jpg",
    },
    {
        "id": "good_vibes",
        "caption": "GOOD VIBES ONLY\n\nLas Terrenas is about to change\n\nThe tropics have a new heartbeat. Crafted cocktails. Warm nights. Real energy. One Love Beach Bar is almost here — are you ready?",
        "fb_caption": "GOOD VIBES ONLY 🌊☀️\n\nLas Terrenas is about to change ✨\n\nThe tropics have a new heartbeat. Crafted cocktails. Warm nights. Real energy. One Love Beach Bar is almost here — are you ready? 🔥\n\n#GoodVibesOnly #OneLoveBeachBar #LasTerrenas #Samana #BeachVibes #TropicalBar #DominicanRepublic #ComingSoon #PlayaBallenas",
        "image_file": "post2-good-vibes.jpg",
    },
    {
        "id": "watch_this_space",
        "caption": "Las Terrenas - Samana - Dominican Republic\n\nWatch this space...\n\nOne Love Beach Bar is coming to Playa Ballenas. Something truly special is being built right on the beach.\n\nFollow us for updates — One Love is almost here!",
        "fb_caption": "Las Terrenas · Samaná · Dominican Republic 🇩🇴\n\nWatch this space... 👀\n\nOne Love Beach Bar is coming to Playa Ballenas. Something truly special is being built right on the beach. 🌴🍹\n\nFollow us for updates — One Love is almost here!\n\n#WatchThisSpace #OneLoveBeachBar #LasTerrenas #Samana #PlayaBallenas #BeachBar #ComingSoon #Caribbean #DominicanRepublic",
        "image_file": "post3-watch-this-space.jpg",
    },
]

DEFAULT_RECIPIENTS = [
    {"phone": "15713410830", "name": "Ash Murthy", "role": "Admin"},
]

DEFAULT_USERS = {
    "admin": {
        "password_hash": hashlib.sha256("OneLove2026!".encode()).hexdigest(),
        "name": "Ash Murthy",
        "role": "admin",
    },
    "asmith": {
        "password_hash": hashlib.sha256("Lasterrenas2026!".encode()).hexdigest(),
        "name": "Abagail Smith",
        "role": "editor",
    }
}

# ══════════════════════════════════════════════
# DATA HELPERS
# ══════════════════════════════════════════════
def load_json(filepath, default):
    if filepath.exists():
        with open(filepath) as f:
            return json.load(f)
    save_json(filepath, default)
    return default

def save_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_config():
    return load_json(CONFIG_FILE, DEFAULT_CONFIG)

def get_posts():
    return load_json(POSTS_FILE, DEFAULT_POSTS)

def get_recipients():
    return load_json(RECIPIENTS_FILE, DEFAULT_RECIPIENTS)

def get_state():
    return load_json(STATE_FILE, {"last_post_index": -1, "posts_sent": 0, "last_post_date": None})

def get_logs():
    return load_json(LOGS_FILE, [])

def get_users():
    saved = load_json(USERS_FILE, DEFAULT_USERS)
    # Merge: ensure any new DEFAULT_USERS are added to existing file
    merged = False
    for username, info in DEFAULT_USERS.items():
        if username not in saved:
            saved[username] = info
            merged = True
    if merged:
        save_json(USERS_FILE, saved)
    return saved

def add_log(entry):
    logs = get_logs()
    logs.insert(0, entry)
    logs = logs[:100]  # Keep last 100
    save_json(LOGS_FILE, logs)

def get_campaign_context():
    return load_json(CAMPAIGN_CONTEXT_FILE, DEFAULT_CAMPAIGN_CONTEXT)

def save_campaign_context(ctx):
    save_json(CAMPAIGN_CONTEXT_FILE, ctx)

def add_generation_record(record):
    """Add a generation record to campaign context history."""
    ctx = get_campaign_context()
    ctx["generation_history"].insert(0, record)
    ctx["generation_history"] = ctx["generation_history"][:50]  # Keep last 50
    save_campaign_context(ctx)

def build_campaign_memory_prompt():
    """Build a system prompt section with campaign memory for GPT calls."""
    ctx = get_campaign_context()
    brand = ctx.get("brand", {})
    posts = get_posts()

    # Brand context
    lines = [
        f"BRAND: {brand.get('name', 'One Love Beach Bar')}",
        f"LOCATION: {brand.get('location', '')}",
        f"VIBE: {brand.get('vibe', '')}",
        f"TONE: {brand.get('tone_of_voice', '')}",
        f"CAMPAIGN PHASE: {ctx.get('campaign_phase', 'pre-launch')}",
        f"CAMPAIGN NOTES: {ctx.get('campaign_notes', '')}",
    ]

    # Style preferences
    prefs = ctx.get("style_preferences", {})
    if prefs.get("preferred_image_styles"):
        lines.append(f"PREFERRED STYLES: {', '.join(prefs['preferred_image_styles'])}")
    if prefs.get("avoided_styles"):
        lines.append(f"AVOID STYLES: {', '.join(prefs['avoided_styles'])}")

    # Brand dos and don'ts
    if brand.get("dos"):
        lines.append("DO: " + " | ".join(brand["dos"]))
    if brand.get("donts"):
        lines.append("DON'T: " + " | ".join(brand["donts"]))

    # Recent posts (short-term memory)
    if posts:
        lines.append(f"\nPREVIOUS POSTS ({len(posts)} total):")
        for p in posts[:10]:  # Last 10 posts
            rating = p.get("rating", "")
            rating_str = f" [RATED: {'LIKED' if rating == 'up' else 'NEEDS IMPROVEMENT'}]" if rating else ""
            lines.append(f"  - [{p['id']}] {p.get('fb_caption', p.get('caption', ''))[:120]}...{rating_str}")

    # Recent generation history with feedback
    history = ctx.get("generation_history", [])
    liked = [h for h in history if h.get("rating") == "up"]
    disliked = [h for h in history if h.get("rating") == "down"]
    if liked:
        lines.append(f"\nSTYLES/PROMPTS USER LIKED ({len(liked)} examples):")
        for h in liked[:5]:
            lines.append(f"  - Prompt: {h.get('prompt', '')[:150]}")
            if h.get("rating_note"):
                lines.append(f"    Note: {h['rating_note']}")
    if disliked:
        lines.append(f"\nSTYLES/PROMPTS USER DISLIKED ({len(disliked)} examples):")
        for h in disliked[:5]:
            lines.append(f"  - Prompt: {h.get('prompt', '')[:150]}")
            if h.get("rating_note"):
                lines.append(f"    Note: {h['rating_note']}")

    return "\n".join(lines)

# ══════════════════════════════════════════════
# JWT AUTH
# ══════════════════════════════════════════════
def create_token(username, name, role):
    """Create a JWT token."""
    payload = {
        "username": username,
        "name": name,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token):
    """Verify a JWT token and return the payload."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def get_token_from_request():
    """Extract JWT token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header[7:]  # Remove "Bearer " prefix

def login_required(f):
    """Decorator to check JWT token in Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_request()
        if not token:
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        payload = verify_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401

        # Store payload info in request context for the handler to use
        request.user = payload
        return f(*args, **kwargs)
    return decorated

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")
    users = get_users()
    user = users.get(username)
    if not user:
        return jsonify({"error": "Invalid username or password"}), 401
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    if pw_hash != user["password_hash"]:
        return jsonify({"error": "Invalid username or password"}), 401

    # Create JWT token
    token = create_token(username, user["name"], user["role"])
    add_log({"time": datetime.now().isoformat(), "action": "login", "username": username})
    return jsonify({
        "ok": True,
        "token": token,
        "name": user["name"],
        "role": user["role"]
    })

@app.route("/api/change-password", methods=["POST"])
@login_required
def change_password():
    data = request.json or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")
    if not current_password or not new_password:
        return jsonify({"error": "Both current and new password are required"}), 400
    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400

    username = request.user.get("username")
    users = get_users()
    user = users.get(username)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Verify current password
    current_hash = hashlib.sha256(current_password.encode()).hexdigest()
    if current_hash != user["password_hash"]:
        return jsonify({"error": "Current password is incorrect"}), 401

    # Update password
    user["password_hash"] = hashlib.sha256(new_password.encode()).hexdigest()
    users[username] = user
    save_json(USERS_FILE, users)
    add_log({"time": datetime.now().isoformat(), "action": "password_changed", "username": username})
    return jsonify({"ok": True, "message": "Password updated successfully"})

@app.route("/api/logout", methods=["POST"])
def logout():
    add_log({"time": datetime.now().isoformat(), "action": "logout"})
    return jsonify({"ok": True})

@app.route("/api/me")
def me():
    token = get_token_from_request()
    if not token:
        return jsonify({"logged_in": False})

    payload = verify_token(token)
    if not payload:
        return jsonify({"logged_in": False})

    return jsonify({
        "logged_in": True,
        "username": payload.get("username"),
        "name": payload.get("name"),
        "role": payload.get("role")
    })

# ══════════════════════════════════════════════
# DASHBOARD / STATUS
# ══════════════════════════════════════════════
@app.route("/api/dashboard")
@login_required
def dashboard():
    config = get_config()
    posts = get_posts()
    recipients = get_recipients()
    state = get_state()
    logs = get_logs()[:10]

    next_idx = (state.get("last_post_index", -1) + 1) % max(len(posts), 1)
    next_post = posts[next_idx] if posts else None

    return jsonify({
        "schedule": {
            "post_time": config["post_time"],
            "interval_days": config["post_interval_days"],
        },
        "stats": {
            "total_posts_sent": state.get("posts_sent", 0),
            "last_post_date": state.get("last_post_date"),
            "last_results": state.get("last_post_results"),
            "total_campaign_posts": len(posts),
            "total_recipients": len(recipients),
        },
        "next_post": {
            "id": next_post["id"] if next_post else None,
            "image_url": config["image_base_url"] + next_post["image_file"] if next_post else None,
        } if next_post else None,
        "recent_logs": logs,
    })

# ══════════════════════════════════════════════
# POSTS CRUD
# ══════════════════════════════════════════════
@app.route("/api/posts")
@login_required
def list_posts():
    config = get_config()
    posts = get_posts()
    for p in posts:
        p["image_url"] = config["image_base_url"] + p["image_file"]
    return jsonify(posts)

@app.route("/api/posts", methods=["POST"])
@login_required
def create_post():
    data = request.json
    if not data or not data.get("id") or not data.get("caption") or not data.get("fb_caption"):
        return jsonify({"error": "Required fields: id, caption, fb_caption"}), 400
    posts = get_posts()
    if any(p["id"] == data["id"] for p in posts):
        return jsonify({"error": f"Post with id '{data['id']}' already exists"}), 400
    post = {
        "id": data["id"].strip().lower().replace(" ", "_"),
        "caption": data["caption"].strip(),
        "fb_caption": data["fb_caption"].strip(),
        "image_file": data.get("image_file", "").strip(),
    }
    posts.append(post)
    save_json(POSTS_FILE, posts)
    # Reset rotation
    state = get_state()
    state["last_post_index"] = -1
    save_json(STATE_FILE, state)
    add_log({"time": datetime.now().isoformat(), "action": "post_created", "post_id": post["id"], "by": request.user.get("name")})
    return jsonify(post), 201

@app.route("/api/posts/<post_id>", methods=["PUT"])
@login_required
def update_post(post_id):
    data = request.json
    posts = get_posts()
    for i, p in enumerate(posts):
        if p["id"] == post_id:
            if data.get("caption"): p["caption"] = data["caption"].strip()
            if data.get("fb_caption"): p["fb_caption"] = data["fb_caption"].strip()
            if data.get("image_file"): p["image_file"] = data["image_file"].strip()
            posts[i] = p
            save_json(POSTS_FILE, posts)
            add_log({"time": datetime.now().isoformat(), "action": "post_updated", "post_id": post_id, "by": request.user.get("name")})
            return jsonify(p)
    return jsonify({"error": "Post not found"}), 404

@app.route("/api/posts/<post_id>", methods=["DELETE"])
@login_required
def delete_post(post_id):
    posts = get_posts()
    posts = [p for p in posts if p["id"] != post_id]
    save_json(POSTS_FILE, posts)
    state = get_state()
    state["last_post_index"] = -1
    save_json(STATE_FILE, state)
    add_log({"time": datetime.now().isoformat(), "action": "post_deleted", "post_id": post_id, "by": request.user.get("name")})
    return jsonify({"ok": True})

# ══════════════════════════════════════════════
# RECIPIENTS CRUD
# ══════════════════════════════════════════════
@app.route("/api/recipients")
@login_required
def list_recipients():
    return jsonify(get_recipients())

@app.route("/api/recipients", methods=["POST"])
@login_required
def add_recipient():
    data = request.json
    phone = (data.get("phone") or "").strip().replace("+", "").replace(" ", "").replace("-", "")
    name = (data.get("name") or "").strip()
    if not phone:
        return jsonify({"error": "Phone number required"}), 400
    recipients = get_recipients()
    if any(r["phone"] == phone for r in recipients):
        return jsonify({"error": "This number is already on the list"}), 400
    entry = {"phone": phone, "name": name, "role": data.get("role", "Contact")}
    recipients.append(entry)
    save_json(RECIPIENTS_FILE, recipients)
    add_log({"time": datetime.now().isoformat(), "action": "recipient_added", "phone": phone, "name": name, "by": request.user.get("name")})
    return jsonify(entry), 201

@app.route("/api/recipients/<phone>", methods=["DELETE"])
@login_required
def remove_recipient(phone):
    recipients = get_recipients()
    recipients = [r for r in recipients if r["phone"] != phone]
    save_json(RECIPIENTS_FILE, recipients)
    add_log({"time": datetime.now().isoformat(), "action": "recipient_removed", "phone": phone, "by": request.user.get("name")})
    return jsonify({"ok": True})

# ══════════════════════════════════════════════
# SCHEDULE / CONFIG
# ══════════════════════════════════════════════
@app.route("/api/config")
@login_required
def get_config_api():
    config = get_config()
    # Don't send full token to frontend — just enough to confirm it's set
    safe = dict(config)
    token = safe.get("page_access_token", "")
    safe["token_preview"] = token[:20] + "..." if len(token) > 20 else "(not set)"
    oai_key = safe.get("openai_api_key", "")
    safe["openai_key_preview"] = oai_key[:12] + "..." if len(oai_key) > 12 else "(not set)"
    gh_token = safe.get("github_token", "")
    safe["github_token_preview"] = gh_token[:12] + "..." if len(gh_token) > 12 else "(not set)"
    safe.pop("page_access_token", None)
    safe.pop("app_secret", None)
    safe.pop("openai_api_key", None)
    safe.pop("github_token", None)
    return jsonify(safe)

@app.route("/api/config", methods=["PUT"])
@login_required
def update_config():
    data = request.json
    config = get_config()
    allowed = ["post_time", "post_interval_days", "report_recipient", "image_base_url",
               "page_access_token", "app_secret", "page_id", "instagram_account_id",
               "wa_phone_number_id", "wa_business_account_id",
               "openai_api_key", "github_token", "github_image_repo"]
    for key in allowed:
        if key in data and data[key] is not None:
            config[key] = data[key]
    save_json(CONFIG_FILE, config)
    add_log({"time": datetime.now().isoformat(), "action": "config_updated", "fields": list(data.keys()), "by": request.user.get("name")})
    return jsonify({"ok": True})

# ══════════════════════════════════════════════
# POSTING ACTIONS
# ══════════════════════════════════════════════
def _do_post_to_facebook(config, caption, image_url):
    token = config["page_access_token"]
    page_id = config["page_id"]
    if image_url:
        url = f"https://graph.facebook.com/v19.0/{page_id}/photos"
        data = {"url": image_url, "caption": caption, "access_token": token}
    else:
        url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
        data = {"message": caption, "access_token": token}
    return http_requests.post(url, data=data).json()

def _do_post_to_instagram(config, caption, image_url):
    token = config["page_access_token"]
    ig_id = config["instagram_account_id"]
    container = http_requests.post(
        f"https://graph.facebook.com/v19.0/{ig_id}/media",
        data={"image_url": image_url, "caption": caption, "access_token": token}
    ).json()
    if "error" in container:
        return container
    time.sleep(5)
    return http_requests.post(
        f"https://graph.facebook.com/v19.0/{ig_id}/media_publish",
        data={"creation_id": container["id"], "access_token": token}
    ).json()

def _do_wa_send_image(config, phone, image_url, caption):
    token = config["page_access_token"]
    phone_id = config["wa_phone_number_id"]
    return http_requests.post(
        f"https://graph.facebook.com/v22.0/{phone_id}/messages",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "messaging_product": "whatsapp", "recipient_type": "individual", "to": phone,
            "type": "image", "image": {"link": image_url, "caption": caption}
        }
    ).json()

def _do_wa_send_text(config, phone, text):
    token = config["page_access_token"]
    phone_id = config["wa_phone_number_id"]
    return http_requests.post(
        f"https://graph.facebook.com/v22.0/{phone_id}/messages",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "messaging_product": "whatsapp", "recipient_type": "individual", "to": phone,
            "type": "text", "text": {"preview_url": False, "body": text}
        }
    ).json()

@app.route("/api/post-now", methods=["POST"])
@login_required
def post_now():
    """Post the next campaign post to all platforms right now."""
    config = get_config()
    posts = get_posts()
    state = get_state()

    if not posts:
        return jsonify({"error": "No campaign posts configured"}), 400

    # Allow posting a specific post by id
    data = request.json or {}
    post_id = data.get("post_id")

    if post_id:
        post = next((p for p in posts if p["id"] == post_id), None)
        if not post:
            return jsonify({"error": f"Post '{post_id}' not found"}), 404
        next_idx = posts.index(post)
    else:
        next_idx = (state.get("last_post_index", -1) + 1) % len(posts)
        post = posts[next_idx]

    image_url = config["image_base_url"] + post["image_file"]
    results = {"post_id": post["id"], "time": datetime.now().isoformat(), "by": request.user.get("name")}

    # Facebook
    fb = _do_post_to_facebook(config, post["fb_caption"], image_url)
    results["facebook"] = "ok" if "error" not in fb else fb.get("error", {}).get("message", "Failed")

    time.sleep(2)

    # Instagram
    ig = _do_post_to_instagram(config, post["fb_caption"], image_url)
    results["instagram"] = "ok" if "error" not in ig else ig.get("error", {}).get("message", "Failed")

    time.sleep(2)

    # WhatsApp broadcast
    recipients = get_recipients()
    wa_sent = 0
    wa_total = len(recipients)
    for r in recipients:
        res = _do_wa_send_image(config, r["phone"], image_url, post["caption"])
        if "error" not in res:
            wa_sent += 1
        time.sleep(1)
    results["whatsapp"] = f"{wa_sent}/{wa_total} delivered"

    # Status report
    report_to = config.get("report_recipient")
    if report_to:
        report = (
            f"*One Love Beach Bar — Post Report*\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"Post: {post['id']}\nTriggered by: {request.user.get('name', 'Dashboard')}\n\n"
            f"Facebook: {results['facebook']}\n"
            f"Instagram: {results['instagram']}\n"
            f"WhatsApp: {results['whatsapp']}"
        )
        _do_wa_send_text(config, report_to, report)

    # Update state
    state["last_post_index"] = next_idx
    state["posts_sent"] = state.get("posts_sent", 0) + 1
    state["last_post_date"] = datetime.now().isoformat()
    state["last_post_results"] = results
    save_json(STATE_FILE, state)

    add_log(results)

    return jsonify(results)

@app.route("/api/post-single", methods=["POST"])
@login_required
def post_single_platform():
    """Post to a single platform only (for testing)."""
    data = request.json or {}
    platform = data.get("platform")  # facebook, instagram, whatsapp
    post_id = data.get("post_id")

    config = get_config()
    posts = get_posts()

    if post_id:
        post = next((p for p in posts if p["id"] == post_id), None)
    else:
        state = get_state()
        next_idx = (state.get("last_post_index", -1) + 1) % max(len(posts), 1)
        post = posts[next_idx] if posts else None

    if not post:
        return jsonify({"error": "Post not found"}), 404

    image_url = config["image_base_url"] + post["image_file"]
    result = {}

    if platform == "facebook":
        fb = _do_post_to_facebook(config, post["fb_caption"], image_url)
        result = {"platform": "facebook", "success": "error" not in fb, "detail": fb}
    elif platform == "instagram":
        ig = _do_post_to_instagram(config, post["fb_caption"], image_url)
        result = {"platform": "instagram", "success": "error" not in ig, "detail": ig}
    elif platform == "whatsapp":
        report_to = config.get("report_recipient", "")
        if report_to:
            wa = _do_wa_send_text(config, report_to, f"Test from One Love Dashboard: {post['id']}")
            result = {"platform": "whatsapp", "success": "error" not in wa, "detail": wa}
        else:
            result = {"platform": "whatsapp", "success": False, "detail": "No report recipient configured"}
    else:
        return jsonify({"error": "Platform must be facebook, instagram, or whatsapp"}), 400

    add_log({"time": datetime.now().isoformat(), "action": f"test_{platform}", "post_id": post["id"], "success": result["success"], "by": request.user.get("name")})
    return jsonify(result)

# ══════════════════════════════════════════════
# LOGS
# ══════════════════════════════════════════════
@app.route("/api/logs")
@login_required
def list_logs():
    return jsonify(get_logs())

# ══════════════════════════════════════════════
# AI IMAGE GENERATION (DALL-E 3)
# ══════════════════════════════════════════════
GENERATED_IMAGES_DIR = DATA_DIR / "generated_images"
GENERATED_IMAGES_DIR.mkdir(exist_ok=True)

@app.route("/api/ai/config")
@login_required
def ai_config():
    """Check if DALL-E API key is configured."""
    config = get_config()
    key = config.get("openai_api_key", "")
    return jsonify({
        "configured": bool(key),
        "key_preview": key[:8] + "..." if len(key) > 8 else "(not set)",
        "github_repo": config.get("github_image_repo", "Ashmurthy64/One-love-bar"),
        "github_token_set": bool(config.get("github_token", "")),
    })

# ══════════════════════════════════════════════
# CAMPAIGN MEMORY ENDPOINTS
# ══════════════════════════════════════════════
@app.route("/api/campaign-context", methods=["GET"])
@login_required
def get_campaign_context_api():
    """Get the full campaign context (brand guidelines, history, etc.)."""
    return jsonify(get_campaign_context())

@app.route("/api/campaign-context", methods=["PUT"])
@login_required
def update_campaign_context_api():
    """Update campaign context fields."""
    data = request.json or {}
    ctx = get_campaign_context()
    # Allow updating specific sections
    for key in ["brand", "campaign_phase", "campaign_notes", "style_preferences"]:
        if key in data:
            if isinstance(data[key], dict) and isinstance(ctx.get(key), dict):
                ctx[key].update(data[key])
            else:
                ctx[key] = data[key]
    save_campaign_context(ctx)
    add_log({"time": datetime.now().isoformat(), "action": "campaign_context_updated", "by": request.user.get("name")})
    return jsonify(ctx)

@app.route("/api/posts/<post_id>/rate", methods=["POST"])
@login_required
def rate_post(post_id):
    """Rate a post (up/down) to teach the AI your preferences."""
    data = request.json or {}
    rating = data.get("rating", "")  # "up" or "down" or "" to clear
    note = data.get("note", "").strip()

    if rating and rating not in ("up", "down"):
        return jsonify({"error": "Rating must be 'up', 'down', or empty"}), 400

    posts = get_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        return jsonify({"error": "Post not found"}), 404

    # Update post rating
    post["rating"] = rating
    post["rating_note"] = note
    save_json(POSTS_FILE, posts)

    # Also update generation history if this post has one
    ctx = get_campaign_context()
    for h in ctx.get("generation_history", []):
        if h.get("post_id") == post_id:
            h["rating"] = rating
            h["rating_note"] = note
            break
    save_campaign_context(ctx)

    add_log({"time": datetime.now().isoformat(), "action": "post_rated", "post_id": post_id, "rating": rating, "note": note, "by": request.user.get("name")})
    return jsonify({"ok": True, "post_id": post_id, "rating": rating})

@app.route("/api/campaign-context/history", methods=["GET"])
@login_required
def get_generation_history():
    """Get the AI generation history."""
    ctx = get_campaign_context()
    return jsonify(ctx.get("generation_history", []))

# ══════════════════════════════════════════════
# AI IMAGE GENERATION ENDPOINTS
# ══════════════════════════════════════════════
@app.route("/api/ai/suggest-prompt", methods=["POST"])
@login_required
def suggest_prompt():
    """Generate an image prompt suggestion based on post caption."""
    data = request.json or {}
    caption = data.get("caption", "")
    style = data.get("style", "tropical beach bar photography")

    if not caption:
        return jsonify({"error": "Caption required"}), 400

    config = get_config()
    api_key = config.get("openai_api_key", "")
    if not api_key:
        return jsonify({"error": "OpenAI API key not configured. Go to Settings to add it."}), 400

    # Build campaign memory context
    memory = build_campaign_memory_prompt()

    # Use GPT to suggest an image prompt — now with full campaign memory
    try:
        resp = http_requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": f"""You are the creative director for One Love Beach Bar. Generate a DALL-E 3 image prompt for a social media post.

CAMPAIGN MEMORY (use this to stay consistent and avoid repetition):
{memory}

RULES:
- Stay visually consistent with previous posts but bring fresh ideas
- If the user liked certain styles before, lean into those
- If the user disliked certain styles, avoid them
- Don't repeat the same compositions as recent posts
- Include specific visual details (lighting, angle, objects, mood)
- Keep it under 200 words
- Return ONLY the prompt, no explanation"""},
                    {"role": "user", "content": f"Create an image prompt for this post caption:\n\n{caption}\n\nStyle preference: {style}"}
                ],
                "max_tokens": 300,
            }
        ).json()
        prompt = resp.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        return jsonify({"prompt": prompt})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ai/generate-image", methods=["POST"])
@login_required
def generate_image():
    """Generate an image using DALL-E 3."""
    data = request.json or {}
    prompt = data.get("prompt", "")
    size = data.get("size", "1024x1024")  # 1024x1024, 1792x1024, 1024x1792
    quality = data.get("quality", "standard")  # standard or hd

    if not prompt:
        return jsonify({"error": "Prompt required"}), 400

    config = get_config()
    api_key = config.get("openai_api_key", "")
    if not api_key:
        return jsonify({"error": "OpenAI API key not configured"}), 400

    try:
        resp = http_requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": size,
                "quality": quality,
                "response_format": "b64_json",
            },
            timeout=120,
        ).json()

        if "error" in resp:
            return jsonify({"error": resp["error"].get("message", "DALL-E error")}), 400

        img_data = resp["data"][0]
        b64 = img_data["b64_json"]
        revised_prompt = img_data.get("revised_prompt", prompt)

        # Save locally with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ai_{timestamp}.png"
        filepath = GENERATED_IMAGES_DIR / filename
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(b64))

        add_log({"time": datetime.now().isoformat(), "action": "ai_image_generated", "filename": filename, "prompt": prompt[:100], "by": request.user.get("name")})

        return jsonify({
            "filename": filename,
            "revised_prompt": revised_prompt,
            "preview_url": f"/api/ai/preview/{filename}",
            "size_bytes": filepath.stat().st_size,
        })

    except http_requests.exceptions.Timeout:
        return jsonify({"error": "Image generation timed out. Try again."}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ai/preview/<filename>")
def preview_image(filename):
    """Serve a generated/imported image preview (no auth - images are non-sensitive)."""
    safe_name = Path(filename).name  # Prevent path traversal
    allowed_ext = {".png", ".jpg", ".jpeg", ".webp"}
    if Path(safe_name).suffix.lower() not in allowed_ext:
        return jsonify({"error": "Invalid file type"}), 400
    return send_from_directory(str(GENERATED_IMAGES_DIR), safe_name)

@app.route("/api/ai/gallery")
@login_required
def ai_gallery():
    """List all generated images."""
    images = []
    for ext in ("*.png", "*.jpg", "*.jpeg"):
        for f in GENERATED_IMAGES_DIR.glob(ext):
            images.append({
                "filename": f.name,
                "preview_url": f"/api/ai/preview/{f.name}",
                "size_bytes": f.stat().st_size,
                "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    images.sort(key=lambda x: x["created"], reverse=True)
    return jsonify(images[:50])  # Last 50


@app.route("/api/ai/import-image", methods=["POST"])
@login_required
def import_external_image():
    """Upload an external image (e.g. from Midjourney) into the gallery."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    # Validate extension
    allowed = {".png", ".jpg", ".jpeg", ".webp"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        return jsonify({"error": f"Unsupported format. Allowed: {', '.join(allowed)}"}), 400

    # Generate safe filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_ext = ".jpg" if ext == ".jpeg" else ext
    dest_name = f"ext_{timestamp}{safe_ext}"
    dest_path = GENERATED_IMAGES_DIR / dest_name

    file.save(str(dest_path))
    size_bytes = dest_path.stat().st_size

    print(f"[import] Imported external image: {dest_name} ({size_bytes} bytes)")

    return jsonify({
        "filename": dest_name,
        "preview_url": f"/api/ai/preview/{dest_name}",
        "size_bytes": size_bytes,
    })

@app.route("/api/ai/upload-to-github", methods=["POST"])
@login_required
def upload_to_github():
    """Upload a generated image to GitHub Pages repo for public hosting."""
    data = request.json or {}
    source_filename = data.get("filename", "")  # The AI-generated file
    target_filename = data.get("target_filename", "")  # What to name it on GitHub

    if not source_filename or not target_filename:
        return jsonify({"error": "Both filename and target_filename required"}), 400

    # Sanitize target filename
    target_filename = re.sub(r'[^a-zA-Z0-9._-]', '-', target_filename)
    if not target_filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        target_filename += '.png'

    config = get_config()
    github_token = config.get("github_token", "")
    github_repo = config.get("github_image_repo", "Ashmurthy64/One-love-bar")

    if not github_token:
        return jsonify({"error": "GitHub token not configured. Go to Settings to add it."}), 400

    source_path = GENERATED_IMAGES_DIR / Path(source_filename).name
    if not source_path.exists():
        return jsonify({"error": "Source image not found"}), 404

    # Read image and base64 encode
    with open(source_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()

    # Upload via GitHub Contents API
    api_url = f"https://api.github.com/repos/{github_repo}/contents/images/{target_filename}"
    try:
        # Check if file exists (to get SHA for update)
        check = http_requests.get(api_url, headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github.v3+json",
        })
        sha = check.json().get("sha") if check.status_code == 200 else None

        payload = {
            "message": f"Add image: {target_filename}",
            "content": content_b64,
            "branch": "main",
        }
        if sha:
            payload["sha"] = sha  # Update existing file

        resp = http_requests.put(api_url, headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }, json=payload)

        if resp.status_code in (200, 201):
            public_url = f"https://ashmurthy64.github.io/One-love-bar/images/{target_filename}"
            add_log({"time": datetime.now().isoformat(), "action": "image_uploaded_github", "filename": target_filename, "url": public_url, "by": request.user.get("name")})
            return jsonify({"url": public_url, "filename": target_filename})
        else:
            return jsonify({"error": f"GitHub API error: {resp.status_code} — {resp.json().get('message', 'Unknown')}"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ai/generate-and-attach", methods=["POST"])
@login_required
def generate_and_attach():
    """Full pipeline: Generate image → Upload to GitHub → Attach to post."""
    data = request.json or {}
    prompt = data.get("prompt", "")
    post_id = data.get("post_id", "")
    target_filename = data.get("target_filename", "")
    size = data.get("size", "1024x1024")
    quality = data.get("quality", "standard")

    if not prompt or not post_id or not target_filename:
        return jsonify({"error": "prompt, post_id, and target_filename required"}), 400

    config = get_config()

    # Step 1: Generate
    gen_resp = generate_image_internal(config, prompt, size, quality)
    if "error" in gen_resp:
        return jsonify(gen_resp), 400

    # Step 2: Upload to GitHub
    upload_resp = upload_to_github_internal(config, gen_resp["filename"], target_filename)
    if "error" in upload_resp:
        return jsonify(upload_resp), 400

    # Step 3: Attach to post
    posts = get_posts()
    for i, p in enumerate(posts):
        if p["id"] == post_id:
            p["image_file"] = target_filename
            posts[i] = p
            save_json(POSTS_FILE, posts)
            break

    # Record generation in campaign memory
    add_generation_record({
        "post_id": post_id,
        "prompt": prompt,
        "revised_prompt": gen_resp.get("revised_prompt", ""),
        "caption_snippet": next((p.get("fb_caption", "")[:100] for p in posts if p["id"] == post_id), ""),
        "filename": target_filename,
        "created_at": datetime.now().isoformat(),
        "rating": "",
        "rating_note": "",
    })

    add_log({"time": datetime.now().isoformat(), "action": "ai_full_pipeline", "post_id": post_id, "filename": target_filename, "by": request.user.get("name")})

    return jsonify({
        "image_url": upload_resp["url"],
        "filename": target_filename,
        "post_id": post_id,
        "revised_prompt": gen_resp.get("revised_prompt", prompt),
    })


@app.route("/api/posts/create-with-ai-image", methods=["POST"])
@login_required
def create_post_with_ai_image():
    """Create a new post and auto-generate an AI image from the caption."""
    data = request.json or {}
    post_id = data.get("id", "").strip().lower().replace(" ", "_")
    caption = data.get("caption", "").strip()
    fb_caption = data.get("fb_caption", "").strip()
    style = data.get("style", "tropical beach bar photography, warm golden hour lighting")
    size = data.get("size", "1024x1024")
    quality = data.get("quality", "standard")

    if not post_id or not caption or not fb_caption:
        return jsonify({"error": "Required fields: id, caption, fb_caption"}), 400

    posts = get_posts()
    if any(p["id"] == post_id for p in posts):
        return jsonify({"error": f"Post with id '{post_id}' already exists"}), 400

    config = get_config()
    api_key = config.get("openai_api_key", "")
    if not api_key:
        return jsonify({"error": "OpenAI API key not configured"}), 400

    # Build campaign memory context
    memory = build_campaign_memory_prompt()

    # Step 1: Generate a DALL-E prompt from the caption using GPT — with campaign memory
    try:
        gpt_resp = http_requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": f"""You are the creative director for One Love Beach Bar. Generate a DALL-E 3 image prompt for a social media post.

CAMPAIGN MEMORY (use this to stay consistent and avoid repetition):
{memory}

RULES:
- Stay visually consistent with previous posts but bring fresh ideas
- If the user liked certain styles before, lean into those
- If the user disliked certain styles, avoid them
- Don't repeat the same compositions as recent posts
- Include specific visual details (lighting, angle, objects, mood)
- Keep it under 200 words
- Return ONLY the prompt, no explanation"""},
                    {"role": "user", "content": f"Create an image prompt for this post caption:\n\n{fb_caption}\n\nStyle preference: {style}"}
                ],
                "max_tokens": 300,
            }
        ).json()
        prompt = gpt_resp.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not prompt:
            return jsonify({"error": "Failed to generate image prompt from caption"}), 500
    except Exception as e:
        return jsonify({"error": f"Prompt generation failed: {str(e)}"}), 500

    # Step 2: Generate image with DALL-E
    gen_resp = generate_image_internal(config, prompt, size, quality)
    if "error" in gen_resp:
        return jsonify(gen_resp), 400

    # Step 3: Upload to GitHub
    target_filename = f"{post_id}.png"
    upload_resp = upload_to_github_internal(config, gen_resp["filename"], target_filename)
    if "error" in upload_resp:
        return jsonify(upload_resp), 400

    # Step 4: Create the post with the image attached
    post = {
        "id": post_id,
        "caption": caption,
        "fb_caption": fb_caption,
        "image_file": upload_resp["filename"],
    }
    posts.append(post)
    save_json(POSTS_FILE, posts)

    # Step 5: Record generation in campaign memory
    add_generation_record({
        "post_id": post_id,
        "prompt": prompt,
        "revised_prompt": gen_resp.get("revised_prompt", ""),
        "style": style,
        "caption_snippet": fb_caption[:100],
        "filename": upload_resp["filename"],
        "created_at": datetime.now().isoformat(),
        "rating": "",
        "rating_note": "",
    })

    state = get_state()
    state["last_post_index"] = -1
    save_json(STATE_FILE, state)

    add_log({"time": datetime.now().isoformat(), "action": "post_created_with_ai", "post_id": post_id, "filename": upload_resp["filename"], "by": request.user.get("name")})

    return jsonify({
        "post": post,
        "image_url": upload_resp["url"],
        "revised_prompt": gen_resp.get("revised_prompt", prompt),
    }), 201


def generate_image_internal(config, prompt, size="1024x1024", quality="standard"):
    """Internal helper for image generation."""
    api_key = config.get("openai_api_key", "")
    if not api_key:
        return {"error": "OpenAI API key not configured"}
    try:
        resp = http_requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "dall-e-3", "prompt": prompt, "n": 1, "size": size, "quality": quality, "response_format": "b64_json"},
            timeout=120,
        ).json()
        if "error" in resp:
            return {"error": resp["error"].get("message", "DALL-E error")}
        img_data = resp["data"][0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ai_{timestamp}.png"
        filepath = GENERATED_IMAGES_DIR / filename
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(img_data["b64_json"]))
        return {"filename": filename, "revised_prompt": img_data.get("revised_prompt", prompt)}
    except Exception as e:
        return {"error": str(e)}


def upload_to_github_internal(config, source_filename, target_filename):
    """Internal helper for GitHub upload."""
    github_token = config.get("github_token", "")
    github_repo = config.get("github_image_repo", "Ashmurthy64/One-love-bar")
    if not github_token:
        return {"error": "GitHub token not configured"}
    target_filename = re.sub(r'[^a-zA-Z0-9._-]', '-', target_filename)
    if not target_filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        target_filename += '.png'
    source_path = GENERATED_IMAGES_DIR / Path(source_filename).name
    if not source_path.exists():
        return {"error": "Source image not found"}
    with open(source_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()
    api_url = f"https://api.github.com/repos/{github_repo}/contents/images/{target_filename}"
    try:
        check = http_requests.get(api_url, headers={"Authorization": f"Bearer {github_token}", "Accept": "application/vnd.github.v3+json"})
        sha = check.json().get("sha") if check.status_code == 200 else None
        payload = {"message": f"Add image: {target_filename}", "content": content_b64, "branch": "main"}
        if sha:
            payload["sha"] = sha
        resp = http_requests.put(api_url, headers={"Authorization": f"Bearer {github_token}", "Accept": "application/vnd.github.v3+json"}, json=payload)
        if resp.status_code in (200, 201):
            return {"url": f"https://ashmurthy64.github.io/One-love-bar/images/{target_filename}", "filename": target_filename}
        else:
            return {"error": f"GitHub API error: {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════
# SCHEDULER (background thread)
# ══════════════════════════════════════════════
scheduler_running = False
scheduler_thread = None

def scheduler_loop():
    global scheduler_running
    import schedule as sched
    config = get_config()
    interval = config["post_interval_days"]
    post_time = config["post_time"]

    def job():
        with app.app_context():
            # Simulate a session for the scheduler
            config = get_config()
            posts = get_posts()
            state = get_state()
            if not posts:
                return
            next_idx = (state.get("last_post_index", -1) + 1) % len(posts)
            post = posts[next_idx]
            image_url = config["image_base_url"] + post["image_file"]
            results = {"post_id": post["id"], "time": datetime.now().isoformat(), "by": "Scheduler"}

            fb = _do_post_to_facebook(config, post["fb_caption"], image_url)
            results["facebook"] = "ok" if "error" not in fb else "failed"
            time.sleep(2)

            ig = _do_post_to_instagram(config, post["fb_caption"], image_url)
            results["instagram"] = "ok" if "error" not in ig else "failed"
            time.sleep(2)

            recipients = get_recipients()
            wa_sent = 0
            for r in recipients:
                res = _do_wa_send_image(config, r["phone"], image_url, post["caption"])
                if "error" not in res: wa_sent += 1
                time.sleep(1)
            results["whatsapp"] = f"{wa_sent}/{len(recipients)} delivered"

            report_to = config.get("report_recipient")
            if report_to:
                report = (
                    f"*One Love Beach Bar — Post Report*\n"
                    f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                    f"Post: {post['id']}\nTriggered by: Scheduler\n\n"
                    f"Facebook: {results['facebook']}\n"
                    f"Instagram: {results['instagram']}\n"
                    f"WhatsApp: {results['whatsapp']}"
                )
                _do_wa_send_text(config, report_to, report)

            state["last_post_index"] = next_idx
            state["posts_sent"] = state.get("posts_sent", 0) + 1
            state["last_post_date"] = datetime.now().isoformat()
            state["last_post_results"] = results
            save_json(STATE_FILE, state)
            add_log(results)

    sched.every(interval).days.at(post_time).do(job)

    while scheduler_running:
        sched.run_pending()
        time.sleep(30)

@app.route("/api/scheduler/start", methods=["POST"])
@login_required
def start_scheduler():
    global scheduler_running, scheduler_thread
    if scheduler_running:
        return jsonify({"status": "already_running"})
    scheduler_running = True
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()
    add_log({"time": datetime.now().isoformat(), "action": "scheduler_started", "by": request.user.get("name")})
    return jsonify({"status": "started"})

@app.route("/api/scheduler/stop", methods=["POST"])
@login_required
def stop_scheduler():
    global scheduler_running
    scheduler_running = False
    add_log({"time": datetime.now().isoformat(), "action": "scheduler_stopped", "by": request.user.get("name")})
    return jsonify({"status": "stopped"})

@app.route("/api/scheduler/status")
@login_required
def scheduler_status():
    return jsonify({"running": scheduler_running})

# ══════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("RAILWAY_ENVIRONMENT") is None  # Debug only when running locally
    print("\n  One Love Beach Bar — Dashboard Server")
    print("  ======================================")
    print(f"  Port: {port}")
    print(f"  API Base: http://localhost:{port}/api")
    print(f"  Frontend: https://ashmurthy64.github.io")
    print(f"  Auth: JWT tokens via /api/login")
    print(f"  Default login: admin / OneLove2026!")
    print(f"  ======================================\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
