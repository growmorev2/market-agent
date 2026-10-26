"""റിപ്പോർട്ട് Telegram-ലേക്കും Discord-ലേക്കും അയക്കുന്ന ഭാഗം.

Secret സെറ്റ് ചെയ്തിട്ടില്ലെങ്കിൽ ആ വഴി ഒഴിവാക്കും (പിശക് കാണിക്കില്ല).
"""
import os
import time

import requests


def split_text(text, limit):
    """നീണ്ട ടെക്സ്റ്റ് വരികൾ മുറിയാതെ ചെറിയ ഭാഗങ്ങളാക്കും."""
    chunks, cur = [], ""
    for line in text.split("\n"):
        while len(line) > limit:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(cur) + len(line) + 1 > limit:
            chunks.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur.strip():
        chunks.append(cur)
    return [c for c in chunks if c.strip()]


def send_telegram(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not (token and chat):
        return "ഒഴിവാക്കി (secret ഇല്ല)"
    for part in split_text(text, 4000):
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": part, "disable_web_page_preview": True},
            timeout=30,
        )
        if r.status_code != 200:
            raise RuntimeError(f"Telegram HTTP {r.status_code}: {r.text[:200]}")
        time.sleep(1)
    return "അയച്ചു"


def send_discord(text):
    hook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not hook:
        return "ഒഴിവാക്കി (secret ഇല്ല)"
    for part in split_text(text, 1900):
        r = requests.post(hook, json={"content": part}, timeout=30)
        if r.status_code == 429:
            time.sleep(float(r.json().get("retry_after", 2)))
            r = requests.post(hook, json={"content": part}, timeout=30)
        if r.status_code not in (200, 204):
            raise RuntimeError(f"Discord HTTP {r.status_code}: {r.text[:200]}")
        time.sleep(1)
    return "അയച്ചു"
