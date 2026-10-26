"""റിസൾട്ട് മുന്നറിയിപ്പ് — അടുത്ത 7 ദിവസത്തിൽ Q റിസൾട്ട് (ബോർഡ് മീറ്റിംഗ്) ഉള്ള സ്റ്റോക്കുകൾ.

ഉറവിടം: NSE-യുടെ event calendar. NSE ചിലപ്പോൾ cloud സെർവറുകളെ തടയും; അപ്പോൾ
3 ദിവസം വരെ പഴയ cache (data/events.json) ഉപയോഗിക്കും. അതും ഇല്ലെങ്കിൽ AI വാർത്ത തിരയലിൽ
റിസൾട്ട് തീയതി നോക്കും (agent.py-യിലെ DRIVERS_DAILY കാണുക).
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

FILE = Path(__file__).resolve().parent.parent / "data" / "events.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-event-calendar",
}
RESULT_WORDS = ("financial result", "results", "quarterly", "audited", "unaudited")


def _parse_date(s):
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def parse_calendar(items):
    """NSE event-calendar JSON → {SYMBOL: 'YYYY-MM-DD'} (റിസൾട്ട് ഉള്ളവ മാത്രം, ഏറ്റവും അടുത്ത തീയതി)."""
    out = {}
    for it in items or []:
        text = f"{it.get('purpose', '')} {it.get('bm_desc', '')}".lower()
        if not any(w in text for w in RESULT_WORDS):
            continue
        sym = (it.get("symbol") or "").strip().upper()
        d = _parse_date(it.get("date") or it.get("bm_date") or "")
        if sym and d:
            ds = d.isoformat()
            if sym not in out or ds < out[sym]:
                out[sym] = ds
    return out


def _fetch():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get("https://www.nseindia.com/", timeout=20)  # cookie എടുക്കാൻ
    r = s.get("https://www.nseindia.com/api/event-calendar", timeout=30)
    r.raise_for_status()
    data = r.json()
    return parse_calendar(data if isinstance(data, list) else data.get("data", []))


def load(today, allow_download=True):
    """{SYMBOL: date} കൂടാതെ ഉറവിട വിവരം."""
    cache = {}
    if FILE.exists():
        cache = json.loads(FILE.read_text(encoding="utf-8"))
    if allow_download:
        try:
            fresh = _fetch()
            if fresh:
                cache = {"fetched": today.isoformat(), "results": fresh}
                FILE.parent.mkdir(parents=True, exist_ok=True)
                FILE.write_text(json.dumps(cache, indent=1), encoding="utf-8")
                return fresh, "NSE"
        except Exception as e:  # noqa: BLE001
            print(f"  NSE event calendar ലഭ്യമായില്ല: {str(e)[:120]}")
    fetched = cache.get("fetched")
    if fetched and today - date.fromisoformat(fetched) <= timedelta(days=3):
        return cache.get("results", {}), f"cache ({fetched})"
    return {}, "none"


def tag(scans, results, today, days=7):
    """അടുത്ത `days` ദിവസത്തിനുള്ളിൽ റിസൾട്ട് ഉള്ളവയ്ക്ക് x['results'] = 'YYYY-MM-DD'."""
    end = (today + timedelta(days=days)).isoformat()
    start = today.isoformat()
    flagged = {}
    for s in scans:
        for x in s["stocks"]:
            d = results.get(x["symbol"].upper())
            if d and start <= d <= end:
                x["results"] = d
                flagged[x["symbol"]] = d
    return dict(sorted(flagged.items(), key=lambda kv: kv[1]))


def short(ds):
    return datetime.strptime(ds, "%Y-%m-%d").strftime("%d %b")
