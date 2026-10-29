"""പ്രശ്നം വന്നാൽ Telegram-ലേക്കും Email-ലേക്കും അറിയിപ്പ് (Python standard library മാത്രം).

Usage:  python3 .github/alert.py "സന്ദേശം"      (അല്ലെങ്കിൽ ALERT_MSG env)
Secrets (ഇല്ലാത്തവ skip ചെയ്യും):
  Telegram: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  Email:    MAIL_USERNAME (Gmail), MAIL_PASSWORD (16-അക്ഷര app password), MAIL_TO
"""
import json
import os
import smtplib
import sys
import urllib.parse
import urllib.request
from email.message import EmailMessage


def send(text, subject="⚠️ Trading automation alert"):
    sent = []
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat:
        try:
            data = urllib.parse.urlencode({"chat_id": chat, "text": text[:4000], "disable_web_page_preview": "true"}).encode()
            urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=30).read()
            sent.append("Telegram")
        except Exception as e:  # noqa: BLE001
            print(f"Telegram alert പരാജയം: {e}")
    user, pw, to = (os.environ.get(k) for k in ("MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_TO"))
    if user and pw and to:
        try:
            m = EmailMessage()
            m["Subject"], m["From"], m["To"] = subject, user, to
            m.set_content(text)
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
                s.login(user, pw.replace(" ", ""))
                s.send_message(m)
            sent.append("Email")
        except Exception as e:  # noqa: BLE001
            print(f"Email alert പരാജയം: {e}")
    print("Alert അയച്ചത്: " + (", ".join(sent) or "ഒന്നുമില്ല (secrets ഇല്ല)"))
    return sent


if __name__ == "__main__":
    msg = " ".join(sys.argv[1:]) or os.environ.get("ALERT_MSG", "")
    if msg:
        send(msg, os.environ.get("ALERT_SUBJECT") or "⚠️ Trading automation alert")
