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


def send_telegram(text, pdf=None, photo=None):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not (token and chat):
        return "ഒഴിവാക്കി (secret ഇല്ല)"
    if photo:
        with open(photo, "rb") as f:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto",
                              data={"chat_id": chat}, files={"photo": (os.path.basename(photo), f, "image/png")}, timeout=60)
        if r.status_code != 200:
            print(f"  Telegram ഗ്രാഫ് പോയില്ല: HTTP {r.status_code}")
    for part in split_text(text, 4000):
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": part, "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=30,
        )
        if r.status_code != 200:
            raise RuntimeError(f"Telegram HTTP {r.status_code}: {r.text[:200]}")
        time.sleep(1)
    if pdf:
        with open(pdf, "rb") as f:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendDocument",
                              data={"chat_id": chat}, files={"document": (os.path.basename(pdf), f, "application/pdf")},
                              timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Telegram PDF HTTP {r.status_code}: {r.text[:200]}")
        return "അയച്ചു (PDF ഉൾപ്പെടെ)"
    return "അയച്ചു"


def send_discord(text, pdf=None, photo=None):
    hook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not hook:
        return "ഒഴിവാക്കി (secret ഇല്ല)"
    from lib.report import to_discord
    text = to_discord(text)
    if photo:
        with open(photo, "rb") as f:
            requests.post(hook, files={"file": (os.path.basename(photo), f, "image/png")}, timeout=60)
    for part in split_text(text, 1900):
        r = requests.post(hook, json={"content": part}, timeout=30)
        if r.status_code == 429:
            time.sleep(float(r.json().get("retry_after", 2)))
            r = requests.post(hook, json={"content": part}, timeout=30)
        if r.status_code not in (200, 204):
            raise RuntimeError(f"Discord HTTP {r.status_code}: {r.text[:200]}")
        time.sleep(1)
    if pdf:
        with open(pdf, "rb") as f:
            r = requests.post(hook, files={"file": (os.path.basename(pdf), f, "application/pdf")}, timeout=60)
        if r.status_code not in (200, 204):
            raise RuntimeError(f"Discord PDF HTTP {r.status_code}: {r.text[:200]}")
        return "അയച്ചു (PDF ഉൾപ്പെടെ)"
    return "അയച്ചു"
