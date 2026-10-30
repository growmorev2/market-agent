"""📦 Order inflow tracker — NSE-ൽ കമ്പനികൾ പ്രഖ്യാപിക്കുന്ന പുതിയ orders ദിവസവും സ്വയം ശേഖരിക്കും.

ഓരോ ദിവസവും (Market Agent-നോടൊപ്പം):
  1. NSE corporate announcements (കഴിഞ്ഞ 7 ദിവസം) — "Bagging/Receiving of orders/contracts",
     "Awarding of order(s)/contract(s)" വിഭാഗങ്ങൾ മാത്രം.
  2. പുതിയവയുടെ PDF വായിച്ച് order value (₹ crore) കണ്ടെത്തും (lib/orders_parse.py).
  3. Chartink: market cap, കഴിഞ്ഞ 4 ക്വാർട്ടറിലെ വിൽപ്പന (TTM) → order ÷ വിൽപ്പന %, order ÷ mcap %.
  4. ഒരേ കമ്പനിയുടെ ഒരേ തുക 15 ദിവസത്തിനുള്ളിൽ വീണ്ടും വന്നാൽ "ആവർത്തനം" (എണ്ണത്തിൽ കൂട്ടില്ല).
  5. വില: announcement-ന് മുമ്പുള്ള close മുതൽ D1 / D5 / D20 — "എന്താണ് ഫലിക്കുന്നത്".
ഫലം: data/orders.json → docs/orders.html (dashboard), Telegram, ⭐ Top conviction.
"""
import io
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

from lib.orders_parse import CONSORTIUM, exec_months, order_value

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "data" / "orders.json"
CATS = ("Bagging/Receiving of orders/contracts", "Awarding of order(s)/contract(s)")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
}
CFG = {"big_pct": 10.0, "fire_pct": 25.0, "min_mcap": 500, "dup_days": 15, "track": 20, "keep_days": 400, "max_pdf": 80}
HORIZONS = (1, 5, 20)
CK_CLAUSE = "( {cash} (  market cap >  100 ) )"
CK_COLS = {"mcap": "Market Cap", "c0": "Daily Close", "c1": "1 day ago Close",
           "ns0": "Quarterly Net Sales", "ns1": "1 quarter ago Net Sales",
           "ns2": "2 quarters ago Net Sales", "ns3": "3 quarters ago Net Sales"}


def load():
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"orders": []}


def _session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get("https://www.nseindia.com/", timeout=20)
    return s


def fetch_announcements(s, today, days=7):
    f = (today - timedelta(days=days)).strftime("%d-%m-%Y")
    t = today.strftime("%d-%m-%Y")
    r = s.get(f"https://www.nseindia.com/api/corporate-announcements?index=equities&from_date={f}&to_date={t}", timeout=40)
    r.raise_for_status()
    return [x for x in r.json() if x.get("desc") in CATS]


def pdf_text(s, url):
    from pypdf import PdfReader
    r = s.get(url, timeout=40)
    if not r.ok or r.content[:4] != b"%PDF":
        return ""
    pdf = PdfReader(io.BytesIO(r.content))
    return " ".join((p.extract_text() or "") for p in pdf.pages[:6])


def fetch_chartink():
    """{SYMBOL: {mcap, c0, c1, ttm}}"""
    from lib import chartink
    s = chartink.new_session()
    r = s.get(f"{chartink.BASE}/screener", timeout=30)
    r.raise_for_status()
    token = chartink._csrf(r.text)
    res = s.post(f"{chartink.BASE}/screener/process",
                 data={"scan_clause": CK_CLAUSE, "column_clause": ",".join(f" {v} as '{k}'" for k, v in CK_COLS.items())},
                 headers={"X-CSRF-TOKEN": token, "X-Requested-With": "XMLHttpRequest", "Referer": f"{chartink.BASE}/screener"},
                 timeout=90)
    res.raise_for_status()
    out = {}
    for row in res.json().get("data") or []:
        def n(k):
            try:
                v = float(row.get(k))
                return None if v != v or abs(v) > 1e15 else v
            except (TypeError, ValueError):
                return None
        ns = [n(f"ns{i}") for i in range(4)]
        out[str(row.get("nsecode"))] = {"mcap": n("mcap"), "c0": n("c0"), "c1": n("c1"),
                                         "ttm": sum(ns) if all(x is not None for x in ns) else None}
    return out


def _an_dt(x):
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M"):
        try:
            return datetime.strptime(x, fmt)
        except (TypeError, ValueError):
            pass
    return None


def run(now, sectors=None, save=True, session=None, ck=None, bdata=None):
    """now = IST datetime. പേജിനും Telegram-നുമുള്ള dict തിരികെ."""
    today = now.date()
    today_s = today.isoformat()
    st = load()
    prev_upd = st.get("updated") or today_s
    have = {o["id"] for o in st["orders"]}
    s = session or _session()
    first = not st["orders"]
    ann = fetch_announcements(s, today, days=90 if first else 7)  # ആദ്യ തവണ: 3 മാസത്തെ ചരിത്രം
    max_pdf = 800 if first else CFG["max_pdf"]
    ck = ck if ck is not None else fetch_chartink()
    added, n_pdf = [], 0
    for x in sorted(ann, key=lambda a: a.get("sort_date") or ""):
        oid = str(x.get("seq_id") or x.get("attchmntFile"))
        if oid in have:
            continue
        dt = _an_dt(x.get("an_dt"))
        sym = x.get("symbol") or ""
        txt = x.get("attchmntText") or ""
        full = ""
        if x.get("attchmntFile") and n_pdf < max_pdf:
            try:
                full = pdf_text(s, x["attchmntFile"])
                n_pdf += 1
                time.sleep(0.3)
            except Exception as e:  # noqa: BLE001
                print(f"  Orders: {sym} PDF വായിക്കാനായില്ല ({str(e)[:60]})")
        val, note = order_value(txt + " " + full, sym)
        title = re.sub(r"\s+", " ", txt).strip()
        title = re.sub(r"^.*?has informed the Exchange about\s*", "", title, flags=re.I)[:220]
        o = {"id": oid, "date": dt.date().isoformat() if dt else today_s, "time": dt.strftime("%H:%M") if dt else "",
             "symbol": sym, "name": x.get("sm_name", ""), "industry": x.get("smIndustry") or "",
             "sector": (sectors or {}).get(sym, ""), "title": title, "value": val, "note": note or "",
             "cons": bool(CONSORTIUM.search(full)), "file": x.get("attchmntFile") or "", "added": today_s}
        c = ck.get(sym) or {}
        o["mcap"] = round(c["mcap"]) if c.get("mcap") else None
        o["ttm"] = round(c["ttm"]) if c.get("ttm") else None
        o["pct_sales"] = round(val / c["ttm"] * 100, 1) if val and c.get("ttm") and c["ttm"] > 0 else None
        o["pct_mcap"] = round(val / c["mcap"] * 100, 1) if val and c.get("mcap") else None
        o["exec_m"] = exec_months(txt + " " + full, dt.date() if dt else today)
        _derive(o)
        # ആവർത്തനം: 15 ദിവസത്തിനുള്ളിൽ ഒരേ കമ്പനി, ഏകദേശം ഒരേ തുക (L1 → LOA)
        lim = (datetime.fromisoformat(o["date"]) - timedelta(days=CFG["dup_days"])).date().isoformat()
        o["dup"] = bool(val) and any(p["symbol"] == sym and p.get("value") and p["date"] >= lim
                                     and abs(p["value"] - val) <= 0.02 * val for p in st["orders"])
        # വില ട്രാക്കിംഗിന്റെ അടിസ്ഥാനം: ഇന്നത്തെ announcement മാത്രം (പഴയവയുടെ കൃത്യമായ close ഇല്ല)
        o["series"] = {}
        o["base"] = None
        if o["date"] == today_s and c.get("c0") and c.get("c1") and now.hour >= 16 and is_trading_day(today, bdata):
            after_close = o["time"] >= "15:30"
            o["base"] = c["c0"] if after_close else c["c1"]
            o["base_date"] = today_s if after_close else "prev"
            if not after_close:
                o["series"][today_s] = c["c0"]
        st["orders"].append(o)
        have.add(oid)
        added.append(o)
    # പഴയ രേഖകൾക്ക് execution കാലാവധി ഇല്ലെങ്കിൽ PDF വീണ്ടും വായിച്ച് ചേർക്കും (ഒറ്റ തവണ)
    n_re = 0
    for o in st["orders"]:
        if "exec_m" in o:
            continue
        if n_re >= 600 or not o.get("file"):
            o.setdefault("exec_m", None)
            _derive(o)
            continue
        try:
            o["exec_m"] = exec_months(pdf_text(s, o["file"]), datetime.fromisoformat(o["date"]).date())
            n_re += 1
            time.sleep(0.2)
        except Exception:  # noqa: BLE001
            o["exec_m"] = None
        _derive(o)
    if n_re:
        print(f"  Orders: {n_re} പഴയ filing-ൽ നിന്ന് execution കാലാവധി ചേർത്തു")
    for o in st["orders"]:
        _derive(o)
    # ദിവസേനയുള്ള വില (20 ട്രേഡിംഗ് ദിവസം വരെ) — ഇന്ന് ശരിക്കും ട്രേഡിംഗ് നടന്നാൽ മാത്രം (NSE അവധി ഒഴിവാക്കും)
    if now.hour >= 16 and is_trading_day(today, bdata):
        for o in st["orders"]:
            if (not o.get("base") or len(o["series"]) >= CFG["track"] or today_s in o["series"]
                    or today_s == o.get("base_date")):
                continue
            c = ck.get(o["symbol"]) or {}
            if c.get("c0"):
                o["series"][today_s] = c["c0"]
    cutoff = (today - timedelta(days=CFG["keep_days"])).isoformat()
    st["orders"] = sorted([o for o in st["orders"] if o["date"] >= cutoff], key=lambda o: (o["date"], o.get("time", "")), reverse=True)
    st["updated"] = today_s
    st["works"] = what_works(st["orders"])
    st["cfg"] = CFG
    if save:
        FILE.write_text(json.dumps(st, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # Telegram-ന്: കഴിഞ്ഞ റണ്ണിന് ശേഷമുള്ളവ മാത്രം (ആദ്യ തവണയിലെ 3 മാസത്തെ ചരിത്രം അല്ല)
    big = [o for o in added if is_big(o) and (o["date"] >= prev_upd if prev_upd != today_s else o["date"] == today_s)]
    print(f"  Orders: NSE-ൽ {len(ann)} order announcement, പുതിയത് {len(added)} (PDF {n_pdf}), വലിയവ {len(big)}")
    return {"updated": today_s, "added": added, "big_today": big, "orders": st["orders"]}


def is_trading_day(today, bdata):
    """GM World-ലെ അവസാന ട്രേഡിംഗ് ദിവസം ഇന്ന് തന്നെയാണോ (അവധി ദിവസം Chartink-ൽ ഇന്നലത്തെ close തന്നെ വരും).
    GM World ഡാറ്റ ഇല്ലെങ്കിൽ: തിങ്കൾ–വെള്ളി."""
    if today.weekday() >= 5:
        return False
    try:
        return datetime.strptime(bdata["asOf"], "%d %b %Y").date() == today
    except (TypeError, KeyError, ValueError):
        return True


def _derive(o):
    """% വിൽപ്പന / വർഷം: പല വർഷത്തെ order-നെ വർഷങ്ങൾ കൊണ്ട് ഭാഗിക്കും (ഒരു വർഷത്തിൽ താഴെയെങ്കിൽ മുഴുവൻ).
    chk: ഉറപ്പാക്കേണ്ടത് — വിൽപ്പനയുടെ 100%+ അല്ലെങ്കിൽ market cap-ന്റെ 50%+."""
    ps, em = o.get("pct_sales"), o.get("exec_m")
    o["pct_year"] = round(ps / max(1.0, (em or 12) / 12), 1) if ps is not None else None
    o["chk"] = bool((ps or 0) > 100 or (o.get("pct_mcap") or 0) > 50)


def is_big(o):
    return bool(o.get("pct_year") and o["pct_year"] >= CFG["big_pct"] and not o.get("dup")
                and (o.get("mcap") or 0) >= CFG["min_mcap"])


def recent_big(orders, today_s, days=30):
    lim = (datetime.fromisoformat(today_s) - timedelta(days=days)).date().isoformat()
    return [o for o in orders if o["date"] >= lim and is_big(o)]


def _ret(o, h):
    c = list(dict(sorted(o.get("series", {}).items())).values())
    return (c[h - 1] / o["base"] - 1) * 100 if o.get("base") and len(c) >= h else None


def what_works(orders):
    groups = [
        ("എല്ലാ orders-ഉം", lambda o: True),
        ("🔥 വർഷ വിൽപ്പനയുടെ 25%+", lambda o: (o.get("pct_year") or 0) >= 25),
        ("വർഷ വിൽപ്പനയുടെ 10–25%", lambda o: 10 <= (o.get("pct_year") or 0) < 25),
        ("10%-ൽ താഴെ", lambda o: o.get("pct_year") is not None and o["pct_year"] < 10),
        ("Value ഇല്ലാത്തവ", lambda o: not o.get("value")),
    ]
    out = []
    for name, f in groups:
        rs = [o for o in orders if not o.get("dup") and f(o)]
        row = {"g": name, "n": len(rs)}
        for h in HORIZONS:
            v = [x for x in (_ret(o, h) for o in rs) if x is not None]
            row[f"d{h}"] = {"n": len(v), "avg": round(sum(v) / len(v), 1) if v else None,
                            "win": round(100 * sum(1 for x in v if x > 0) / len(v)) if v else None}
        out.append(row)
    return out


def telegram_line(res):
    """✅ ഇന്നത്തെ action-ൽ ചേർക്കാൻ: ഇന്നത്തെ വലിയ orders."""
    if not res or not res.get("big_today"):
        return ""
    bits = [f"{o['symbol']} ₹{o['value']:,.0f} cr ({o['pct_year']:.0f}% വർഷ വിൽപ്പന{' 🔥' if o['pct_year'] >= CFG['fire_pct'] else ''}"
            f"{' ⚠️' if o.get('chk') else ''})"
            for o in sorted(res["big_today"], key=lambda o: -o["pct_year"])[:6]]
    return "🏗️ വലിയ orders: " + ", ".join(bits)
