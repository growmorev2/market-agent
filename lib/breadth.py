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
            "above": {k: pct_above(data, k) for k in ("e20", "d50", "d200")},
            "mstat": market_status(data)}


def message_line(sig, fresh=True):
    s = (f"{sig['emoji']} മാർക്കറ്റ്: {sig['label']}, {sig['trend']} "
         f"(20: {sig['t20']:.0f} · 50: {sig['t50']:.0f} · 200: {sig['t200']:.0f} · NH-NL {sig['nh']:+.1f}%)")
    if not fresh:
        s += f" — {sig['asOf']}-ലെ ഡാറ്റ"
    return s


SECTOR_NAMES = {"i.t": "IT", "fmcg": "FMCG", "telecom-service": "Telecom Services"}


def nice_sector(k):
    return SECTOR_NAMES.get(k, k.title().replace("&", "&").replace(" And ", " & "))


def sector_moves(data, back=5, top=5):
    """Landry Momentum by sector: ഇന്നത്തെ മൂല്യം, `back` സെഷൻ മുമ്പത്തേതിൽ നിന്നുള്ള മാറ്റം."""
    rows = []
    for k, v in (data.get("sectors") or {}).items():
        if k in ("n/a", "indices") or not v:
            continue
        before = v[-1 - back] if len(v) > back else v[0]
        rows.append({"sector": nice_sector(k), "now": v[-1], "change": v[-1] - before})
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
    ms = sig.get("mstat")
    if ms:
        c = ms["cycle"]
        lines.append(f"Market status (dashboard): {ms['name']} = market cycle {c['cond']} ({c['n']}/{c['tot']} "
                     f"timeframes with more stocks above than below the MA; "
                     + ", ".join(f"{t['name']} {t['ma']}: {t['state']}" for t in c["tfs"])
                     + f") x sentiment {ms['sentiment']} (breadth {ms['breadth']}, MSWING momentum {ms['momentum']})")
    mv = sector_moves(data)
    fmt = lambda rs: ", ".join(f"{r['sector']} {r['now']} ({r['change']:+d})" for r in rs) or "none"
    lines.append("Sector momentum (Landry, count of stocks; change vs 5 sessions ago):")
    lines.append("  Highest now: " + fmt(mv["leaders"]))
    lines.append("  Rising most: " + fmt(mv["gainers"]))
    lines.append("  Falling most: " + fmt(mv["losers"]))
    return "\n".join(lines)


# ---------- Market status (GM World ഡാഷ്‌ബോർഡിലെ അതേ നിയമങ്ങൾ) ----------
# Market cycle: 20/50/200 DMA-ക്ക് മുകളിലും താഴെയുമുള്ള സ്റ്റോക്കുകളുടെ crossover എണ്ണം
# Market sentiment: Breadth (Net NH−NL) × Momentum (Homma MSWING)
# Market status: ഇവ രണ്ടും ചേർത്ത്. index.html-ൽ മാറ്റം വരുത്തിയാൽ ഇവിടെയും മാറ്റണം.
CYC_TF = [("e20", "Short", "20"), ("d50", "Medium", "50"), ("d200", "Long", "200")]
CYC_LOOK, CYC_FRESH = 3, 3
CYC_ST = {"down": "Markdown", "acc": "Accumulation", "xbull": "Bull crossover",
          "up": "Markup", "dist": "Distribution", "xbear": "Bear crossover"}


def _cycle_one(m):
    up, dn = m["up"], m["dn"]
    spread = [100 * (u - d) / (u + d) if (u + d) else 0 for u, d in zip(up, dn)]
    prev, last_x, st = True, None, None
    for i, s in enumerate(spread):
        d = s - spread[max(0, i - CYC_LOOK)]
        blue_gain = True if d > 0 else False if d < 0 else prev
        prev = blue_gain
        if i > 0 and (spread[i - 1] < 0) != (s < 0):
            last_x = (i, s >= 0)
        st = ("up" if blue_gain else "dist") if s >= 0 else ("acc" if blue_gain else "down")
        if last_x and i - last_x[0] < CYC_FRESH:
            st = "xbull" if last_x[1] else "xbear"
    return {"lead": spread[-1] >= 0, "state": CYC_ST[st]}


def market_cycle(data):
    ma = data.get("ma") or {}
    tfs = [(name, n, _cycle_one(ma[k])) for k, name, n in CYC_TF if ma.get(k)]
    if not tfs:
        return None
    tot, n_bull = len(tfs), sum(1 for _, _, c in tfs if c["lead"])
    cond = ("Strong bull" if n_bull == tot else "Bull condition" if n_bull * 2 > tot
            else "Turning" if n_bull else "Bear condition")
    return {"cond": cond, "n": n_bull, "tot": tot, "lv": min(3, round(n_bull * 3 / tot)),
            "tfs": [{"name": name, "ma": n, "state": c["state"]} for name, n, c in tfs]}


def _breadth_state(nh):
    n, pos3 = nh[-1], len(nh) >= 3 and all(x > 0 for x in nh[-3:])
    if pos3 and n > 5:
        return 3, "Strong"
    if pos3:
        return 2, "Healthy"
    if n > 0:
        return 1, "Improving"
    return 0, "Weak"


def _momentum_state(hom, ahom):
    v, avg = hom[-1], ahom[-1]
    above, rising = v > avg, len(hom) > 1 and v > hom[-2]
    if v > 50 and above and rising:
        return 3, "Strong"
    if v > 50 and above:
        return 3, "Strong · Choppy"
    if v > 50:
        return 1, "Slowing"
    if above and rising:
        return 2, "Turning"
    if above:
        return 2, "Turning · Choppy"
    return 0, "Negative"


SENT = [["Bearish", "Weakening", "Recovering", "Recovering"],
        ["Mixed", "Cautious", "Improving", "Improving"],
        ["Mixed", "Cautious", "Building", "Bullish"],
        ["Mixed", "Cautious", "Building", "Very bullish"]]
SENT_GROUP = {"Bearish": 0, "Weakening": 0, "Mixed": 1, "Cautious": 1, "Recovering": 2,
              "Improving": 2, "Building": 2, "Bullish": 3, "Very bullish": 3}
MSTAT = [[("Stay out", "🔴"), ("Wait", "🔴"), ("Bottoming", "🔵"), ("Early rally", "🔵")],
         [("Failed turn", "🔴"), ("Wait", "🟠"), ("Early uptrend", "🔵"), ("Uptrend starting", "🟢")],
         [("Correction", "🟠"), ("Pullback", "🟠"), ("Uptrend", "🟢"), ("Uptrend", "🟢")],
         [("Topping risk", "🟠"), ("Pullback", "🟠"), ("Uptrend", "🟢"), ("Strong uptrend", "🟩")]]
MSTAT_ML = {
    "Stay out": "എല്ലാം ദുർബലം. പുതിയ ട്രേഡ് വേണ്ട.",
    "Wait": "വ്യക്തമായ ദിശയില്ല. crossover-നോ നല്ല sentiment-നോ കാത്തിരിക്കുക.",
    "Bottoming": "ഇപ്പോഴും താഴെ, പക്ഷേ momentum തിരിയുന്നു. ചെറിയ ടെസ്റ്റ് ട്രേഡുകൾ മാത്രം.",
    "Early rally": "crossover ആയില്ല, പക്ഷേ sentiment ശക്തം. ശ്രദ്ധയോടെ തുടങ്ങാം.",
    "Failed turn": "ഒരു crossover വന്നു, പക്ഷേ sentiment ദുർബലം. തിരിച്ചുവീഴാൻ സാധ്യത.",
    "Early uptrend": "പുതിയ സൈക്കിൾ തുടങ്ങുന്നു. പൊസിഷൻ പതുക്കെ കൂട്ടാം.",
    "Uptrend starting": "നല്ല sentiment-ഓടെ പുതിയ സൈക്കിൾ. പൊസിഷൻ കൂട്ടാം.",
    "Uptrend": "ട്രെൻഡ് ആരോഗ്യകരം. സാധാരണ പൊസിഷൻ സൈസ്.",
    "Strong uptrend": "ട്രെൻഡും sentiment-ഉം ശക്തം. പൂർണ്ണ പൊസിഷൻ സൈസ്.",
    "Pullback": "ട്രെൻഡ് മുകളിൽ, പക്ഷേ ക്ഷീണം. പുതിയ buy സൂക്ഷിച്ച്.",
    "Correction": "ട്രെൻഡ് മുകളിൽ, പക്ഷേ sentiment നെഗറ്റീവ്. Stop മുറുക്കുക, ലാഭം എടുക്കുക.",
    "Topping risk": "മൂന്നും crossover ആയി, പക്ഷേ sentiment നെഗറ്റീവ്. Stop മുറുക്കുക, ലാഭം എടുക്കുക.",
}


def market_status(data):
    """ഡാഷ്‌ബോർഡിലെ Market status. ഡാറ്റ ഇല്ലെങ്കിൽ None."""
    try:
        cyc = market_cycle(data)
        if not cyc or not data.get("nh") or not data.get("hom") or not data.get("ahom"):
            return None
        bl, bname = _breadth_state(data["nh"])
        ml, mname = _momentum_state(data["hom"], data["ahom"])
        sent = SENT[bl][ml]
        name, emoji = MSTAT[cyc["lv"]][SENT_GROUP[sent]]
        return {"name": name, "emoji": emoji, "meaning": MSTAT_ML[name], "cycle": cyc,
                "sentiment": sent, "breadth": bname, "momentum": mname}
    except Exception as e:  # noqa: BLE001
        print(f"  Market status കണക്കാക്കാനായില്ല: {str(e)[:120]}")
        return None
