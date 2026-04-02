#!/usr/bin/env python3
"""
One Love Beach Bar — Auto-Posting Agent
Posts to Instagram, Facebook, and WhatsApp every other day, rotating through campaign content.
Sends a WhatsApp status report after each posting run.

Requirements:
    pip install requests schedule

Setup:
    1. Set environment variables or update CONFIG below
    2. Add recipient phone numbers to WHATSAPP_RECIPIENTS
    3. Run: python post_agent.py
"""

import os
import json
import time
import requests
from datetime import datetime
from pathlib import Path

# ══════════════════════════════════════════════
# CONFIG — fill these in
# ══════════════════════════════════════════════
CONFIG = {
    # Meta App credentials (from developers.facebook.com)
    "app_id": "1669620497794638",
    "app_secret": os.getenv("META_APP_SECRET", "YOUR_APP_SECRET"),

    # Page Access Token (System User token — never expires)
    # NOTE: This token must have whatsapp_business_messaging permission
    #       for WhatsApp to work. Add it in Meta Business Suite > System Users.
    "page_access_token": os.getenv("PAGE_ACCESS_TOKEN", "EAAXugtCuRk4BROJpyFxoJN6uohZAe7KdCectbYHdLYhmaficZCkdiCyQXX369Vx7CBZB0cGZAY6stp2JGtvcNbWbvqWqW3TYWa42ahQOsR2gyXkJNICZAAW7vPyJaxeA3Pv3BZAFfLuOk3LLkHWzgppXOdUfkN6dqq89uMcPZCfMiMPLZAq7Fc6ZADsbONvp7NU7gmAZDZD"),

    # Facebook Page ID (One Love Beach Bar)
    "page_id": os.getenv("PAGE_ID", "1005826949287918"),

    # Instagram Business Account ID (linked to the page)
    "instagram_account_id": os.getenv("IG_ACCOUNT_ID", "17841439106843704"),

    # WhatsApp Business API
    "wa_phone_number_id": os.getenv("WA_PHONE_NUMBER_ID", "990492627489867"),
    "wa_business_account_id": os.getenv("WA_BUSINESS_ACCOUNT_ID", "1325691766278431"),

    # Post every other day at this time
    "post_time": "10:00",  # 10 AM Dominican Republic time (UTC-4)
    "post_interval_days": 2,
}

# WhatsApp recipients — phone numbers in international format (no + or spaces)
# Example: "18091234567" for a Dominican Republic number
# These contacts must have opted in or messaged your WhatsApp Business number first.
WHATSAPP_RECIPIENTS = [
    "15713410830",  # One Love Beach Bar WhatsApp Business number
]

# Phone number to receive the posting status report via WhatsApp
# Leave empty to skip reporting; set to your own number to get notified
REPORT_RECIPIENT = os.getenv("WA_REPORT_TO", "15713410830")  # Ash's reporting number

# ══════════════════════════════════════════════
# CONTENT ROTATION — campaign posts & captions
# ══════════════════════════════════════════════
POSTS = [
    {
        "id": "coming_soon",
        "caption": (
            "Something Special Is Coming\n\n"
            "One Love Beach Bar is almost ready to open its doors on Playa Ballenas. "
            "Tropical cocktails, warm vibes and good energy right on the beach.\n\n"
            "Stay tuned — One Love is coming to Las Terrenas, Samana"
        ),
        "fb_caption": (
            "✦ Something Special Is Coming ✦\n\n"
            "One Love Beach Bar is almost ready to open its doors on Playa Ballenas. "
            "🌴 Tropical cocktails, warm vibes and good energy right on the beach.\n\n"
            "Stay tuned — One Love is coming to Las Terrenas, Samaná 🇩🇴🍹\n\n"
            "#OneLoveBeachBar #LasTerrenas #Samana #PlayaBallenas #ComingSoon "
            "#TropicalCocktails #DominicanRepublic #BeachBar #Caribbean"
        ),
        "image_file": "post1-coming-soon.jpg",
    },
    {
        "id": "good_vibes",
        "caption": (
            "GOOD VIBES ONLY\n\n"
            "Las Terrenas is about to change\n\n"
            "The tropics have a new heartbeat. Crafted cocktails. Warm nights. Real energy. "
            "One Love Beach Bar is almost here — are you ready?"
        ),
        "fb_caption": (
            "GOOD VIBES ONLY 🌊☀️\n\n"
            "Las Terrenas is about to change ✨\n\n"
            "The tropics have a new heartbeat. Crafted cocktails. Warm nights. Real energy. "
            "One Love Beach Bar is almost here — are you ready? 🔥\n\n"
            "#GoodVibesOnly #OneLoveBeachBar #LasTerrenas #Samana #BeachVibes "
            "#TropicalBar #DominicanRepublic #ComingSoon #PlayaBallenas"
        ),
        "image_file": "post2-good-vibes.jpg",
    },
    {
        "id": "watch_this_space",
        "caption": (
            "Las Terrenas - Samana - Dominican Republic\n\n"
            "Watch this space...\n\n"
            "One Love Beach Bar is coming to Playa Ballenas. "
            "Something truly special is being built right on the beach.\n\n"
            "Follow us for updates — One Love is almost here!"
        ),
        "fb_caption": (
            "Las Terrenas · Samaná · Dominican Republic 🇩🇴\n\n"
            "Watch this space... 👀\n\n"
            "One Love Beach Bar is coming to Playa Ballenas. "
            "Something truly special is being built right on the beach. 🌴🍹\n\n"
            "Follow us for updates — One Love is almost here!\n\n"
            "#WatchThisSpace #OneLoveBeachBar #LasTerrenas #Samana "
            "#PlayaBallenas #BeachBar #ComingSoon #Caribbean #DominicanRepublic"
        ),
        "image_file": "post3-watch-this-space.jpg",
    },
]

# Track which post to use next
state_file = Path("agent_state.json")

def load_state():
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {"last_post_index": -1, "posts_sent": 0, "last_post_date": None}

def save_state(state):
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

def get_next_post(state):
    next_idx = (state["last_post_index"] + 1) % len(POSTS)
    return POSTS[next_idx], next_idx

# ══════════════════════════════════════════════
# FACEBOOK POSTING
# ══════════════════════════════════════════════
def post_to_facebook(caption: str, image_url: str = None) -> dict:
    """Post to Facebook Page with optional image."""
    token = CONFIG["page_access_token"]
    page_id = CONFIG["page_id"]

    if image_url:
        url = f"https://graph.facebook.com/v19.0/{page_id}/photos"
        data = {"url": image_url, "caption": caption, "access_token": token}
    else:
        url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
        data = {"message": caption, "access_token": token}

    response = requests.post(url, data=data)
    result = response.json()

    if "error" in result:
        print(f"  Facebook FAILED: {result['error']['message']}")
    else:
        print(f"  Facebook OK — Post ID: {result.get('id', 'N/A')}")

    return result

# ══════════════════════════════════════════════
# INSTAGRAM POSTING
# ══════════════════════════════════════════════
def post_to_instagram(caption: str, image_url: str) -> dict:
    """Post to Instagram Business Account."""
    token = CONFIG["page_access_token"]
    ig_id = CONFIG["instagram_account_id"]

    # Step 1: Create media container
    container_url = f"https://graph.facebook.com/v19.0/{ig_id}/media"
    container_data = {"image_url": image_url, "caption": caption, "access_token": token}
    container_response = requests.post(container_url, data=container_data).json()

    if "error" in container_response:
        print(f"  Instagram container FAILED: {container_response['error']['message']}")
        return container_response

    container_id = container_response.get("id")
    print(f"  Instagram container created: {container_id}")

    # Step 2: Wait for container to be ready
    time.sleep(5)

    # Step 3: Publish
    publish_url = f"https://graph.facebook.com/v19.0/{ig_id}/media_publish"
    publish_data = {"creation_id": container_id, "access_token": token}
    publish_response = requests.post(publish_url, data=publish_data).json()

    if "error" in publish_response:
        print(f"  Instagram publish FAILED: {publish_response['error']['message']}")
    else:
        print(f"  Instagram OK — Post ID: {publish_response.get('id', 'N/A')}")

    return publish_response

# ══════════════════════════════════════════════
# WHATSAPP BUSINESS API
# ══════════════════════════════════════════════
def wa_send_image(to_phone: str, image_url: str, caption: str) -> dict:
    """Send an image with caption to a WhatsApp number via Cloud API."""
    token = CONFIG["page_access_token"]
    phone_id = CONFIG["wa_phone_number_id"]

    url = f"https://graph.facebook.com/v22.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption,
        },
    }

    response = requests.post(url, headers=headers, json=payload)
    result = response.json()

    if "error" in result:
        print(f"  WhatsApp to {to_phone} FAILED: {result['error'].get('message', result['error'])}")
    else:
        msg_id = result.get("messages", [{}])[0].get("id", "N/A")
        print(f"  WhatsApp to {to_phone} OK — Message ID: {msg_id}")

    return result


def wa_send_text(to_phone: str, text: str) -> dict:
    """Send a plain text message to a WhatsApp number."""
    token = CONFIG["page_access_token"]
    phone_id = CONFIG["wa_phone_number_id"]

    url = f"https://graph.facebook.com/v22.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }

    response = requests.post(url, headers=headers, json=payload)
    result = response.json()

    if "error" in result:
        print(f"  WhatsApp text to {to_phone} FAILED: {result['error'].get('message', result['error'])}")
    else:
        msg_id = result.get("messages", [{}])[0].get("id", "N/A")
        print(f"  WhatsApp text to {to_phone} OK — Message ID: {msg_id}")

    return result


def post_to_whatsapp(caption: str, image_url: str) -> list:
    """Send campaign image + caption to all opted-in WhatsApp recipients."""
    if not WHATSAPP_RECIPIENTS:
        print("  WhatsApp — no recipients configured, skipping broadcast.")
        return []

    results = []
    for phone in WHATSAPP_RECIPIENTS:
        result = wa_send_image(phone, image_url, caption)
        results.append({"phone": phone, "result": result})
        time.sleep(1)  # Small delay to avoid rate limits

    return results

# ══════════════════════════════════════════════
# STATUS REPORT (sent via WhatsApp)
# ══════════════════════════════════════════════
def send_status_report(post_id: str, fb_result: dict, ig_result: dict, wa_results: list):
    """Send a summary report to the admin via WhatsApp after each posting run."""
    if not REPORT_RECIPIENT:
        print("  Report — no report recipient configured, skipping.")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    fb_ok = "error" not in fb_result
    ig_ok = "error" not in ig_result
    wa_sent = sum(1 for r in wa_results if "error" not in r.get("result", {}))
    wa_total = len(wa_results)

    lines = [
        f"*One Love Beach Bar — Post Report*",
        f"Time: {now}",
        f"Post: {post_id}",
        f"",
        f"Facebook: {'Sent' if fb_ok else 'FAILED'}",
        f"Instagram: {'Sent' if ig_ok else 'FAILED'}",
    ]

    if wa_total > 0:
        lines.append(f"WhatsApp: {wa_sent}/{wa_total} delivered")
    else:
        lines.append(f"WhatsApp: No recipients configured")

    # Add error details if any failed
    if not fb_ok:
        lines.append(f"\nFB error: {fb_result.get('error', {}).get('message', 'Unknown')}")
    if not ig_ok:
        lines.append(f"\nIG error: {ig_result.get('error', {}).get('message', 'Unknown')}")

    report_text = "\n".join(lines)
    print(f"\n  Sending status report to {REPORT_RECIPIENT}...")
    wa_send_text(REPORT_RECIPIENT, report_text)

# ══════════════════════════════════════════════
# MAIN POSTING JOB
# ══════════════════════════════════════════════
def run_post_job():
    """Main job — picks next post and publishes to FB + Instagram + WhatsApp."""
    print(f"\n{'='*55}")
    print(f"  One Love Beach Bar — Auto-Posting Agent")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*55}\n")

    state = load_state()
    post, next_idx = get_next_post(state)

    image_url = f"https://ashmurthy64.github.io/One-love-bar/images/{post['image_file']}"

    print(f"  Post: {post['id']}")
    print(f"  Image: {image_url}\n")

    # ---- Facebook (uses fb_caption with emojis/hashtags) ----
    print("[1/4] Facebook...")
    fb_result = post_to_facebook(post["fb_caption"], image_url)

    time.sleep(3)

    # ---- Instagram (uses fb_caption with emojis/hashtags) ----
    print("[2/4] Instagram...")
    ig_result = post_to_instagram(post["fb_caption"], image_url)

    time.sleep(3)

    # ---- WhatsApp broadcast (uses plain caption, no hashtags) ----
    print("[3/4] WhatsApp broadcast...")
    wa_results = post_to_whatsapp(post["caption"], image_url)

    time.sleep(2)

    # ---- WhatsApp status report to admin ----
    print("[4/4] Status report...")
    send_status_report(post["id"], fb_result, ig_result, wa_results)

    # Update state
    state["last_post_index"] = next_idx
    state["posts_sent"] += 1
    state["last_post_date"] = datetime.now().isoformat()
    state["last_post_results"] = {
        "fb": "ok" if "error" not in fb_result else "failed",
        "ig": "ok" if "error" not in ig_result else "failed",
        "wa_sent": sum(1 for r in wa_results if "error" not in r.get("result", {})),
        "wa_total": len(wa_results),
    }
    save_state(state)

    print(f"\n  Done! Total posts sent: {state['posts_sent']}\n")

# ══════════════════════════════════════════════
# SCHEDULER
# ══════════════════════════════════════════════
def start_scheduler():
    """Run the agent on a schedule — every other day at configured time."""
    import schedule as sched

    post_time = CONFIG["post_time"]
    interval = CONFIG["post_interval_days"]

    print(f"  One Love Beach Bar Auto-Posting Agent Started")
    print(f"  Schedule: Every {interval} days at {post_time}")
    print(f"  Platforms: Facebook + Instagram + WhatsApp")
    print(f"  Content: {len(POSTS)} posts rotating")
    print(f"  WhatsApp recipients: {len(WHATSAPP_RECIPIENTS)}")
    print(f"  Report to: {REPORT_RECIPIENT or '(none)'}\n")

    sched.every(interval).days.at(post_time).do(run_post_job)

    # Run immediately on first start
    print("  Running first post now...\n")
    run_post_job()

    while True:
        sched.run_pending()
        time.sleep(60)

# ══════════════════════════════════════════════
# TOKEN HELPER — generate Page Access Token
# ══════════════════════════════════════════════
def get_page_access_token():
    """
    Helper to exchange a short-lived user token for a long-lived page token.
    Run this once to get your permanent page access token.
    """
    user_token = input("Enter your short-lived User Access Token from Graph API Explorer: ").strip()

    url = "https://graph.facebook.com/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": CONFIG["app_id"],
        "client_secret": CONFIG["app_secret"],
        "fb_exchange_token": user_token,
    }
    r = requests.get(url, params=params).json()
    long_lived_token = r.get("access_token")
    print(f"\n  Long-lived user token: {long_lived_token[:20]}...")

    pages_url = "https://graph.facebook.com/me/accounts"
    r2 = requests.get(pages_url, params={"access_token": long_lived_token}).json()

    print("\n  Your Pages and Tokens:")
    for page in r2.get("data", []):
        print(f"\n  Page: {page['name']}")
        print(f"  Page ID: {page['id']}")
        print(f"  Page Access Token: {page['access_token'][:30]}...")

    for page in r2.get("data", []):
        if "One Love" in page["name"]:
            page_token = page["access_token"]
            ig_url = f"https://graph.facebook.com/{page['id']}"
            ig_r = requests.get(ig_url, params={
                "fields": "instagram_business_account",
                "access_token": page_token
            }).json()
            ig_id = ig_r.get("instagram_business_account", {}).get("id")
            if ig_id:
                print(f"\n  Instagram Business Account ID: {ig_id}")

# ══════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    usage = """
Usage:
    python post_agent.py            Start the scheduler (runs every 2 days)
    python post_agent.py test       Post once immediately (all platforms)
    python post_agent.py wa-test    Send a test WhatsApp message to REPORT_RECIPIENT
    python post_agent.py get-token  Helper to generate a long-lived Page Access Token
    python post_agent.py status     Show current agent state
"""

    if len(sys.argv) < 2:
        start_scheduler()

    elif sys.argv[1] == "test":
        run_post_job()

    elif sys.argv[1] == "wa-test":
        if not REPORT_RECIPIENT:
            print("Set REPORT_RECIPIENT or WA_REPORT_TO env var first.")
            sys.exit(1)
        print(f"Sending test message to {REPORT_RECIPIENT}...")
        result = wa_send_text(REPORT_RECIPIENT, "One Love Beach Bar agent is online and ready!")
        print(json.dumps(result, indent=2))

    elif sys.argv[1] == "get-token":
        get_page_access_token()

    elif sys.argv[1] == "status":
        state = load_state()
        print(json.dumps(state, indent=2))

    else:
        print(usage)
