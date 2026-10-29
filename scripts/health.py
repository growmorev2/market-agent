"""ദിവസ പരിശോധന (8:17 PM IST, തിങ്കൾ–വെള്ളി) — workflow "പച്ച" ആയാലും ഉള്ളിൽ പ്രശ്നം ഉണ്ടോ എന്ന് നോക്കും.

പരിശോധിക്കുന്നത്:
  1. GM World: ഇന്നത്തെ ഡാറ്റ വന്നോ
  2. Market Agent: ഇന്നത്തെ റിപ്പോർട്ട്, സ്കാനർ പിശകുകൾ, Strategy (വില, Fair Value), PEAD
  3. Screener Summary: ഇന്നത്തെ valuations, problems.txt
  4. ഇന്നത്തെ GitHub workflow റണ്ണുകളിൽ പരാജയം
പ്രശ്നം ഉണ്ടെങ്കിൽ മാത്രം Telegram + Email (.github/alert.py). എല്ലാം ശരിയാണെങ്കിൽ ഒന്നും അയക്കില്ല.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github"))
from alert import send  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
GM_RAW = "https://raw.githubusercontent.com/growmorev2/gm-world/main/index.html"
SCREENER = os.environ.get("SCREENER_REPO") or "growmorev2/screener-summery"


def get(url, token=None, raw=False):
    h = {"User-Agent": "market-agent-health", "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def main():
    now = datetime.now(IST)
    today = now.date().isoformat()
    if now.weekday() >= 5 and not os.environ.get("FORCE"):
        print("വാരാന്ത്യം — പരിശോധന ഇല്ല")
        return 0
    issues, stale = [], 0

    # 1. GM World
    try:
        m = re.search(r'"asOf":"([^"]+)"', get(GM_RAW + f"?t={int(now.timestamp())}"))
        asof = datetime.strptime(m.group(1), "%d %b %Y").date().isoformat() if m else None
        if asof != today:
            issues.append(f"GM World: ഇന്നത്തെ ഡാറ്റ വന്നില്ല (അവസാനം {asof or '?'})")
            stale += 1
    except Exception as e:  # noqa: BLE001
        issues.append(f"GM World പേജ് വായിക്കാനായില്ല: {str(e)[:100]}")

    # 2. Market Agent
    if not (ROOT / "docs" / "reports" / f"{today}.html").exists():
        issues.append("Market Agent: ഇന്നത്തെ റിപ്പോർട്ട് ഉണ്ടായില്ല")
        stale += 1
    hist = ROOT / "data" / "history" / f"{today}.json"
    if hist.exists():
        h = json.loads(hist.read_text(encoding="utf-8"))
        for s in h.get("scans", []):
            if s.get("error"):
                issues.append(f"സ്കാനർ പിശക് — {s['name']}: {s['error'][:120]}")
    sp = ROOT / "docs" / "strategy.html"
    if sp.exists():
        try:
            d = json.loads(re.search(r'id="sdata">(.*?)</script>', sp.read_text(encoding="utf-8"), re.S).group(1).replace("<\\/", "</"))
            if d.get("date") != today:
                issues.append(f"Strategy പേജ് ഇന്ന് പുതുക്കിയില്ല (അവസാനം {d.get('date')})")
            else:
                if (d.get("prices") or 0) < 50:
                    issues.append(f"Strategy: വില കിട്ടിയത് {d.get('prices')} സ്റ്റോക്കിന് മാത്രം (Chartink indicators?)")
                if not d.get("have_val"):
                    issues.append("Strategy: Fair Value ബന്ധിപ്പിക്കാനായില്ല (SCREENER_TOKEN കാലഹരണപ്പെട്ടോ?)")
                if not d.get("pead"):
                    issues.append("PEAD ട്രാക്കർ ഇന്ന് ഓടിയില്ല")
        except Exception as e:  # noqa: BLE001
            issues.append(f"Strategy പേജ് വായിക്കാനായില്ല: {str(e)[:100]}")

    # 3. Screener Summary (private repo — SCREENER_TOKEN)
    token = (os.environ.get("SCREENER_TOKEN") or "").strip()
    if token:
        base = f"https://api.github.com/repos/{SCREENER}/contents/output"
        try:
            v = json.loads(get(f"{base}/valuations.json", token, raw=True))
            if v.get("updated") != today:
                issues.append(f"Screener Summary: ഇന്ന് ഓടിയില്ല / പൂർത്തിയായില്ല (അവസാനം {v.get('updated')})")
                stale += 1
        except Exception as e:  # noqa: BLE001
            issues.append(f"Screener Summary വായിക്കാനായില്ല: {str(e)[:100]}")
        try:
            probs = [x for x in get(f"{base}/problems.txt", token, raw=True).splitlines() if x.strip()]
            if probs:
                issues.append(f"Screener Summary-ൽ {len(probs)} പ്രശ്നം: " + "; ".join(probs[:3])[:250])
        except Exception:  # noqa: BLE001  (404 = പ്രശ്നമില്ല)
            pass

    # 4. ഇന്നത്തെ workflow റണ്ണുകൾ
    gh = os.environ.get("GITHUB_TOKEN")
    since = (now - timedelta(hours=14)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for repo, tok in (("growmorev2/market-agent", gh), ("growmorev2/gm-world", None)):
        try:
            runs = json.loads(get(f"https://api.github.com/repos/{repo}/actions/runs?created=%3E%3D{since}&per_page=50", tok))
            bad = [r for r in runs.get("workflow_runs", []) if r.get("conclusion") == "failure"
                   and "pages" not in (r.get("name") or "").lower()]
            for r in bad[:3]:
                issues.append(f"{repo.split('/')[1]}: '{r['name']}' പരാജയപ്പെട്ടു — {r['html_url']}")
        except Exception as e:  # noqa: BLE001
            print(f"{repo} റൺ ലിസ്റ്റ് കിട്ടിയില്ല: {e}")

    if not issues:
        print("✅ എല്ലാം ശരി")
        return 0
    head = f"⚠️ ദിവസ പരിശോധന ({now:%d %b}) — {len(issues)} പ്രശ്നം"
    body = head + "\n\n" + "\n".join(f"• {x}" for x in issues)
    if stale >= 2:
        body += "\n\n(ഇന്ന് മാർക്കറ്റ് അവധി ദിവസമാണെങ്കിൽ ഇത് അവഗണിക്കുക.)"
    body += "\n\nറണ്ണുകൾ: https://github.com/growmorev2/market-agent/actions"
    print(body)
    send(body, head)
    return 0


if __name__ == "__main__":
    sys.exit(main())
