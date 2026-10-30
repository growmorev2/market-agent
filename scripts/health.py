"""ദിവസ പരിശോധന (8:17 PM IST, തിങ്കൾ–വെള്ളി) — workflow "പച്ച" ആയാലും ഉള്ളിൽ പ്രശ്നം ഉണ്ടോ എന്ന് നോക്കും.

പരിശോധിക്കുന്നത്:
  1. GM World: ഇന്നത്തെ ഡാറ്റ വന്നോ
  2. Market Agent: ഇന്നത്തെ റിപ്പോർട്ട്, സ്കാനർ പിശകുകൾ + എണ്ണത്തിലെ വലിയ മാറ്റം (>50%), Strategy (വില, Fair Value), PEAD
  3. Screener Summary: ഇന്നത്തെ valuations, problems.txt
  4. ഇന്നത്തെ GitHub workflow റണ്ണുകളിൽ പരാജയം
  5. Screener Summary (private) Actions minutes: 70% ഉപയോഗിച്ചാൽ / മാസാവസാനം 90% കടക്കുമെന്ന് കണ്ടാൽ
പ്രശ്നം ഉണ്ടെങ്കിൽ മാത്രം Telegram + Email (.github/alert.py). എല്ലാം ശരിയാണെങ്കിൽ ഒന്നും അയക്കില്ല.
ഒരേ പ്രശ്നം: ആദ്യ ദിവസം അയക്കും, പിന്നെ 3 ദിവസത്തിലൊരിക്കൽ മാത്രം (data/health_state.json). ശരിയായാൽ "✅ ശരിയായി" എന്ന് അടുത്ത സന്ദേശത്തിൽ.
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


STATE = ROOT / "data" / "health_state.json"
MINUTES_LIMIT = 2000  # GitHub Free: private repos-ന് മാസം 2,000 മിനിറ്റ് (Linux)


def actions_minutes(repo, token, now):
    """ഈ മാസത്തെ റണ്ണുകളുടെ ആകെ സമയം (മിനിറ്റ്, ഓരോ job-ഉം മുകളിലേക്ക് റൗണ്ട് ചെയ്ത് — GitHub ബിൽ ചെയ്യുന്ന രീതി)."""
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).strftime("%Y-%m-%d")
    total, page = 0.0, 1
    while page <= 10:
        runs = json.loads(get(f"https://api.github.com/repos/{repo}/actions/runs?created=%3E%3D{start}&per_page=100&page={page}", token))
        for r in runs.get("workflow_runs", []):
            if r.get("run_started_at") and r.get("updated_at"):
                a = datetime.fromisoformat(r["run_started_at"].replace("Z", "+00:00"))
                b = datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00"))
                total += max(1, -(-(b - a).total_seconds() // 60))
        if len(runs.get("workflow_runs", [])) < 100:
            break
        page += 1
    return total
REMIND_DAYS = 3


def issue_key(text):
    """അക്കങ്ങളും തീയതികളും മാറ്റി ഒരേ പ്രശ്നത്തിന് ഒരേ key (ഉദാ: "അവസാനം 2026-10-29" → "അവസാനം #")."""
    return re.sub(r"https?://\S+", "", re.sub(r"\d+([.,:/-]\d+)*", "#", text)).strip()[:160]


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(st):
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


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
        prev_files = sorted(x for x in (ROOT / "data" / "history").glob("*.json") if x.stem < today)
        prev = {}
        if prev_files:
            try:
                prev = {s.get("slug") or s["name"]: len(s.get("stocks") or [])
                        for s in json.loads(prev_files[-1].read_text(encoding="utf-8")).get("scans", []) if not s.get("error")}
            except Exception:  # noqa: BLE001
                prev = {}
        for s in h.get("scans", []):
            if s.get("error"):
                issues.append(f"സ്കാനർ പിശക് — {s['name']}: {s['error'][:120]}")
                continue
            # ഡാറ്റ ശരിയാണോ: ഇന്നലത്തെ എണ്ണവുമായി 50%-ൽ കൂടുതൽ വ്യത്യാസം / 0 ആയാൽ അലർട്ട്
            n, p0 = len(s.get("stocks") or []), prev.get(s.get("slug") or s["name"])
            if p0 is None:
                continue
            if n == 0 and p0 > 0:
                issues.append(f"സ്കാനർ {s['name']}: ഇന്ന് 0 സ്റ്റോക്ക് (ഇന്നലെ {p0}) — Chartink ഡാറ്റ?")
            elif p0 >= 10 and abs(n - p0) / p0 > 0.5:
                issues.append(f"സ്കാനർ {s['name']}: എണ്ണം {p0} → {n} (50%-ൽ കൂടുതൽ മാറ്റം) — ഒന്ന് നോക്കുക")
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

    # 2a. Order inflow tracker
    op = ROOT / "data" / "orders.json"
    if op.exists():
        try:
            if json.loads(op.read_text(encoding="utf-8")).get("updated") != today:
                issues.append("Order tracker: ഇന്ന് NSE announcements എടുക്കാനായില്ല")
        except Exception as e:  # noqa: BLE001
            issues.append(f"data/orders.json വായിക്കാനായില്ല: {str(e)[:80]}")

    # 2b. TradingView watchlists (GitHub)
    tvp = ROOT / "tv" / "last_run.json"
    if tvp.exists():
        try:
            t = json.loads(tvp.read_text(encoding="utf-8"))
            run_day = (datetime.strptime(t["run"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).astimezone(IST)).date().isoformat()
            if run_day != today:
                issues.append(f"TradingView watchlists: ഇന്ന് ഓടിയില്ല (അവസാനം {run_day})")
            elif not t.get("tv_login"):
                issues.append("TradingView watchlists: GitHub Secrets-ൽ TV_SESSIONID / TV_SESSIONID_SIGN ഇല്ല")
            bad = {k: v for k, v in (t.get("tv") or {}).items() if v != 200}
            if bad:
                issues.append(f"TradingView watchlists: list {', '.join(bad)} പുതുക്കാനായില്ല (login കാലഹരണപ്പെട്ടോ?)")
        except Exception as e:  # noqa: BLE001
            issues.append(f"tv/last_run.json വായിക്കാനായില്ല: {str(e)[:80]}")

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

    # 3b. GitHub Actions minutes (private repo മാത്രം limit — മാസം 2,000 മിനിറ്റ് സൗജന്യം)
    if token:
        try:
            used = actions_minutes(SCREENER, token, now)
            day = now.day
            proj = used / max(day, 1) * 30
            print(f"Actions minutes ({SCREENER}): ഈ മാസം {used:.0f}, മാസാവസാനം ഏകദേശം {proj:.0f} / {MINUTES_LIMIT}")
            if used >= 0.7 * MINUTES_LIMIT or (day >= 7 and proj >= 0.9 * MINUTES_LIMIT):
                issues.append(f"GitHub Actions minutes: Screener Summary ഈ മാസം {used:.0f} മിനിറ്റ് ഉപയോഗിച്ചു, "
                              f"മാസാവസാനം ഏകദേശം {proj:.0f} / {MINUTES_LIMIT} — limit അടുക്കുന്നു")
        except Exception as e:  # noqa: BLE001
            print(f"Actions minutes കണക്കാക്കാനായില്ല: {e}")

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

    # ഒരേ പ്രശ്നം ദിവസവും അയക്കില്ല: പുതിയ പ്രശ്നം → ഉടൻ; തുടരുന്നത് → 3 ദിവസത്തിലൊരിക്കൽ ഓർമ്മപ്പെടുത്തൽ
    state = load_state()
    new, still, keep = [], [], {}
    for x in issues:
        k = issue_key(x)
        first, last = state.get(k, {}).get("first", today), state.get(k, {}).get("last")
        keep[k] = {"first": first, "last": last, "text": x[:200]}
        if last is None:
            new.append(x)
            keep[k]["last"] = today
        elif (now.date() - datetime.fromisoformat(last).date()).days >= REMIND_DAYS:
            days = (now.date() - datetime.fromisoformat(first).date()).days
            still.append(f"{x} (🔁 {days} ദിവസമായി)")
            keep[k]["last"] = today
    fixed = [v["text"] for k, v in state.items() if k not in keep]
    save_state(keep)
    if fixed:
        print("ശരിയായവ: " + "; ".join(fixed))
    if not new and not still:
        print("✅ പുതിയ പ്രശ്നമില്ല" + (f" (തുടരുന്നവ {len(issues)}, ഓർമ്മപ്പെടുത്തൽ പിന്നീട്)" if issues else ""))
        return 0
    head = f"⚠️ ദിവസ പരിശോധന ({now:%d %b}) — " + (f"{len(new)} പുതിയ പ്രശ്നം" if new else "ഓർമ്മപ്പെടുത്തൽ")
    body = head + "\n\n" + "\n".join(f"• {x}" for x in new + still)
    if fixed:
        body += "\n\n✅ ശരിയായി: " + "; ".join(f[:80] for f in fixed[:4])
    if stale >= 2:
        body += "\n\n(ഇന്ന് മാർക്കറ്റ് അവധി ദിവസമാണെങ്കിൽ ഇത് അവഗണിക്കുക.)"
    body += "\n\nറണ്ണുകൾ: https://github.com/growmorev2/market-agent/actions"
    print(body)
    send(body, head)
    return 0


if __name__ == "__main__":
    sys.exit(main())
