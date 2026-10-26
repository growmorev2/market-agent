"""GM World മാർക്കറ്റ് ബ്രെഡ്ത്ത് + മാർക്കറ്റ് അവസ്ഥ സിഗ്നൽ (🟢🟡🔴).

ഡാറ്റ നിങ്ങളുടെ gm-world repo-യിലെ index.html-ൽ നിന്ന് നേരിട്ട് വായിക്കും
(/*DATA-START*/ ... /*DATA-END*/ ബ്ലോക്ക്). അത് എല്ലാ ദിവസവും ~5:30 PM-ന് പുതുക്കുന്നു;
അതുകൊണ്ട് ഈ ഏജന്റ് 6:13 PM-ന് ഓടുന്നു, ഇന്നത്തെ ഡാറ്റ വന്നില്ലെങ്കിൽ കുറച്ച് നേരം കാത്തിരിക്കും.

GM World-ലെ അതേ സോണുകൾ: >80 Extended, >50 Strong, 20–50 Choppy, <20 Near the bottom.
സിഗ്നൽ നിയമങ്ങൾ താഴെ signal()-ൽ — ആവശ്യമെങ്കിൽ അക്കങ്ങൾ മാറ്റാം.
"""
import json
import os
import re
import time
from datetime import date, datetime

import requests

DEFAULT_URL = "https://raw.githubusercontent.com/growmorev2/gm-world/main/index.html"
BLOCK = re.compile(r"/\*DATA-START\*/\s*const DATA\s*=\s*(\{.*?\})\s*;?\s*/\*DATA-END\*/", re.S)

NAMES = {"t20": "Short (20)", "t50": "Medium (50)", "t200": "Long (200)", "hom": "Homma"}
AVG = {"t20": "a20", "t50": "a50", "t200": "a200", "hom": "ahom"}


def zone(v):
    return "Extended" if v > 80 else "Strong" if v > 50 else "Choppy" if v >= 20 else "Near the bottom"


ZONE_ML = {"Extended": "അമിതമായി ഉയർന്നത്", "Strong": "ശക്തം", "Choppy": "അസ്ഥിരം", "Near the bottom": "അടിത്തട്ടിനടുത്ത്"}


def parse(html):
    m = BLOCK.search(html)
    if not m:
        raise RuntimeError("GM World പേജിൽ DATA ബ്ലോക്ക് കണ്ടെത്തിയില്ല")
    return json.loads(m.group(1))


def as_of(data):
    return datetime.strptime(data["asOf"], "%d %b %Y").date()


def fetch(url=None):
    url = url or (os.environ.get("GMWORLD_URL") or "").strip() or DEFAULT_URL
    r = requests.get(url, params={"t": int(time.time())}, timeout=30,
                     headers={"Cache-Control": "no-cache", "User-Agent": "market-agent"})
    r.raise_for_status()
    return parse(r.text)


def load_fresh(today, wait_minutes=None):
    """ഇന്നത്തെ ഡാറ്റ വരുന്നത് വരെ (പരമാവധി wait_minutes) കാത്തിരിക്കും. തിരികെ: data, fresh?"""
    if wait_minutes is None:
        wait_minutes = float(os.environ.get("GMWORLD_WAIT_MIN") or 20)
    deadline = time.time() + wait_minutes * 60
    data = None
    while True:
        try:
            data = fetch()
            if as_of(data) >= today:
                return data, True
            print(f"  GM World ഇപ്പോഴും {data['asOf']} — കാത്തിരിക്കുന്നു…")
        except Exception as e:  # noqa: BLE001
            print(f"  GM World ലഭ്യമായില്ല: {str(e)[:120]}")
        if time.time() + 120 > deadline:
            return data, False
        time.sleep(120)


def _last(a, i=1):
    return a[-i] if len(a) >= i else None


def pct_above(data, key):
    ma = (data.get("ma") or {}).get(key)
    if not ma:
        return None
    u, d = ma["up"][-1], ma["dn"][-1]
    return round(100 * u / (u + d)) if (u + d) else None


def signal(data):
    t20, t50, nh = _last(data["t20"]), _last(data["t50"]), _last(data["nh"])
    a20, prev20 = _last(data["a20"]), _last(data["t20"], 2)

    if t50 < 20 or (t20 < 20 and nh < 0):
        level, emoji, label = "red", "🔴", "ദുർബലം"
    elif t20 > 50 and t50 > 50 and nh > 0:
        level, emoji, label = "green", "🟢", "ആരോഗ്യകരം"
    else:
        level, emoji, label = "yellow", "🟡", "മിശ്രം"

    if t20 > a20 and prev20 is not None and t20 > prev20:
        trend = "മെച്ചപ്പെടുന്നു"
    elif t20 < a20 and prev20 is not None and t20 < prev20:
        trend = "ദുർബലമാകുന്നു"
    else:
        trend = "മാറ്റമില്ലാതെ"

    notes = []
    if t20 > 80:
        notes.append("Short (20) 80-ന് മുകളിൽ — അമിതമായി ഉയർന്ന നില")
    if t20 < 20:
        notes.append("Short (20) 20-ന് താഴെ — അടിത്തട്ടിനടുത്തുള്ള നില")

    return {"level": level, "emoji": emoji, "label": label, "trend": trend, "notes": notes,
            "asOf": data["asOf"], "t20": t20, "t50": t50, "t200": _last(data["t200"]),
            "hom": _last(data["hom"]), "nh": nh,
            "above": {k: pct_above(data, k) for k in ("e20", "d50", "d200")}}


def message_line(sig, fresh=True):
    s = (f"{sig['emoji']} മാർക്കറ്റ്: {sig['label']}, {sig['trend']} "
         f"(20: {sig['t20']:.0f} · 50: {sig['t50']:.0f} · 200: {sig['t200']:.0f} · NH-NL {sig['nh']:+.1f}%)")
    if not fresh:
        s += f" — {sig['asOf']}-ലെ ഡാറ്റ"
    return s


def sector_moves(data, back=5, top=5):
    """Landry Momentum by sector: ഇന്നത്തെ മൂല്യം, `back` സെഷൻ മുമ്പത്തേതിൽ നിന്നുള്ള മാറ്റം."""
    rows = []
    for k, v in (data.get("sectors") or {}).items():
        if k in ("n/a", "indices") or not v:
            continue
        before = v[-1 - back] if len(v) > back else v[0]
        rows.append({"sector": k, "now": v[-1], "change": v[-1] - before})
    leaders = sorted(rows, key=lambda r: -r["now"])[:top]
    gainers = sorted((r for r in rows if r["change"] > 0), key=lambda r: -r["change"])[:top]
    losers = sorted((r for r in rows if r["change"] < 0), key=lambda r: r["change"])[:top]
    return {"leaders": leaders, "gainers": gainers, "losers": losers}


def table(data, sessions=5):
    """കഴിഞ്ഞ `sessions` സെഷനുകൾ: [(date, {key: value})]"""
    n = min(sessions, len(data["dates"]))
    out = []
    for i in range(-n, 0):
        out.append((data["dates"][i], {k: data[k][i] for k in ("t20", "t50", "t200", "hom", "nh")}))
    return out


def prompt_text(data, fresh=True, sessions=5):
    sig = signal(data)
    lines = [f"Market condition (from the trader's GM World breadth dashboard, as of {data['asOf']}"
             + ("" if fresh else ", NOT updated today") + f"): {sig['level'].upper()}, trend: {sig['trend']}"]
    for k, name in NAMES.items():
        v, a = data[k][-1], data[AVG[k]][-1]
        lines.append(f"- {name}: {v} (5-day avg {a}; zone {zone(v)})")
    lines.append(f"- Net new highs - new lows % (252 day): {data['nh'][-1]}%")
    ab = {k: v for k, v in sig["above"].items() if v is not None}
    if ab:
        lines.append("- Stocks above: " + ", ".join(f"{ {'e20': '20 EMA', 'd50': '50 DMA', 'd200': '200 DMA'}[k]} {v}%" for k, v in ab.items()))
    lines.append("Last sessions (date: short20/medium50/long200/homma/netNHNL):")
    for d, v in table(data, sessions):
        lines.append(f"  {d}: {v['t20']}/{v['t50']}/{v['t200']}/{v['hom']}/{v['nh']}")
    mv = sector_moves(data)
    fmt = lambda rs: ", ".join(f"{r['sector']} {r['now']} ({r['change']:+d})" for r in rs) or "none"
    lines.append("Sector momentum (Landry, count of stocks; change vs 5 sessions ago):")
    lines.append("  Highest now: " + fmt(mv["leaders"]))
    lines.append("  Rising most: " + fmt(mv["gainers"]))
    lines.append("  Falling most: " + fmt(mv["losers"]))
    return "\n".join(lines)
