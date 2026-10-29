"""PEAD tracker — Excellent റിസൾട്ട് വന്ന സ്റ്റോക്കുകൾ, റിസൾട്ട് ദിവസം മുതൽ ഓരോ ദിവസവും വില എത്ര % മാറി.

ഓരോ ദിവസവും:
  1. റിസൾട്ട് തീയതികൾ: NSE event calendar (data/events.json) data/results_log.json-ൽ ചേർത്തുവെക്കും
     (NSE വരാനിരിക്കുന്നവ മാത്രം തരുന്നതുകൊണ്ട് കഴിഞ്ഞുപോയ തീയതികൾ ഈ log-ൽ നിന്ന്)
  2. Chartink: net profit വളരുന്ന (YoY) liquid സ്റ്റോക്കുകൾ — കഴിഞ്ഞ 12 ദിവസത്തെ close, ക്വാർട്ടർ profit / sales
  3. കഴിഞ്ഞ 5 ട്രേഡിംഗ് ദിവസത്തിൽ റിസൾട്ട് വന്നവയിൽ, Chartink പുതിയ ക്വാർട്ടർ ചേർത്ത ശേഷം,
     Excellent ആയവ data/pead.json-ൽ ചേർക്കും
  4. ലിസ്റ്റിലുള്ള ഓരോന്നിനും: റിസൾട്ടിന് മുമ്പുള്ള close (base) മുതൽ ഓരോ ദിവസത്തെയും % മാറ്റം
     — 60 ട്രേഡിംഗ് ദിവസം (≈3 മാസം) വരെ, പിന്നെ "പൂർത്തിയായവ"-ലേക്ക്

Excellent (7 പരിശോധന, 1-ഉം 2-ഉം 3-ഉം നിർബന്ധം, ആകെ 5 എങ്കിലും):
  1 EPS growth YoY ≥ 30%   2 Sales growth YoY ≥ 15%
  3 Quality of earnings: core profit (PBT − other income) YoY ≥ 20% — other income / ഒറ്റത്തവണ നേട്ടം കൊണ്ടുള്ള ലാഭം ഒഴിവാക്കാൻ
  4 EPS acceleration (ഈ Q-ന്റെ YoY > മുൻ Q-ന്റെ YoY)   5 QoQ profit growth
  6 Record quarter (5 ക്വാർട്ടറിലെ ഉയർന്ന profit)       7 Real growth (ഒരു വർഷം മുമ്പും ലാഭം)
ലേബലുകൾ മാത്രം (Excellent തീരുമാനിക്കുന്നതിൽ ഇല്ല, വിശകലനത്തിന്):
  • SUE (Standardized Unexpected Earnings) = (ഈ Q-ന്റെ YoY profit മാറ്റം − മുൻ 8 Q-ന്റെ ശരാശരി മാറ്റം) / അവയുടെ standard deviation
  • മാർക്കറ്റ് പ്രതികരണം: റിസൾട്ട് ദിവസത്തെ / പിറ്റേന്നത്തെ വില % + volume (50 ദിവസ ശരാശരിയുടെ എത്ര ഇരട്ടി)
  • Margin: core EBITDA margin (PBT − other income + interest + depreciation) / sales, മുൻ വർഷത്തെ അതേ Q-നെക്കാൾ
EPS: Chartink-ൽ ക്വാർട്ടർ EPS ഇല്ല — ക്വാർട്ടർ net profit growth ആണ് EPS growth ആയി എടുക്കുന്നത്.
ഇത് സാമ്പത്തിക ഉപദേശമല്ല.
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "results_log.json"
STATE = ROOT / "data" / "pead.json"
SEEN = ROOT / "data" / "pead_seen.json"  # ഓരോ സ്റ്റോക്കിന്റെയും ക്വാർട്ടർ profit (Chartink പുതുക്കിയോ എന്ന് അറിയാൻ)
EVENTS = ROOT / "data" / "events.json"

CFG = {"eps_min": 30.0, "sales_min": 15.0, "core_min": 20.0, "need": 5, "add_window": 5, "track_days": 60,
       "react_min": 4.0, "vol_min": 2.0, "base_warn": 150.0}
N = 12  # എത്ര ദിവസം പിന്നിലേക്കുള്ള വില

CLAUSE = ("( {cash} (  market cap >  500 and  daily sma(  daily volume , 10 ) *  daily sma(  daily close , 10 ) >=  10000000"
          " and  quarterly net profit/reported profit after tax >  0"
          " and  quarterly net profit/reported profit after tax >  4 quarters ago net profit/reported profit after tax ) )")


def _ago(k, field):
    return f"Daily {field}" if k == 0 else f"1 day ago {field}" if k == 1 else f"{k} days ago {field}"


NP = "Net Profit/Reported Profit After Tax"
COL_SETS = [
    {f"c{k}": _ago(k, "Close") for k in range(N + 1)},
    {**{f"l{k}": _ago(k, "Low") for k in range(N)}, **{f"v{k}": _ago(k, "Volume") for k in range(N)}},
    {"av50": "Daily Sma( Volume , 50 )", "e20": "Daily Ema( Close , 20 )", "s50": "Daily Sma( Close , 50 )",
     "np0": f"Quarterly {NP}", "np1": f"1 quarter ago {NP}", "np2": f"2 quarters ago {NP}", "np3": f"3 quarters ago {NP}",
     "np4": f"4 quarters ago {NP}", "np5": f"5 quarters ago {NP}",
     "ns0": "Quarterly Net Sales", "ns4": "4 quarters ago Net Sales"},
    {**{f"np{k}": f"{k} quarters ago {NP}" for k in range(6, 13)},
     "oi0": "Quarterly Other Income", "oi4": "4 quarters ago Other Income",
     "pbt0": "Quarterly Profit Before Tax", "pbt4": "4 quarters ago Profit Before Tax",
     "in0": "Quarterly Interest", "in4": "4 quarters ago Interest",
     "dp0": "Quarterly Depreciation", "dp4": "4 quarters ago Depreciation"},
]


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) < 1e15 else None  # NaN / inf / Chartink-ന്റെ "ഡാറ്റ ഇല്ല" (1.7e308) → ഇല്ല


def fetch(session=None):
    """Chartink-ൽ നിന്ന് {SYMBOL: {c0.., l0.., v0.., av50, e20, s50, np0.., ns0..}}."""
    from lib import chartink
    s = session or chartink.new_session()
    out = {}
    for cols in COL_SETS:
        rows = _process(s, chartink, ",".join(f" {v} as '{k}'" for k, v in cols.items()))
        for row in rows:
            sym = row.get("nsecode")
            if sym:
                d = out.setdefault(str(sym), {"name": row.get("name", "")})
                for k in cols:
                    d[k] = _num(row.get(k))
    return out


def _process(s, chartink, cols):
    token = getattr(s, "_ck_token", None)
    if not token:
        r = s.get(f"{chartink.BASE}/screener", timeout=30)
        r.raise_for_status()
        token = s._ck_token = chartink._csrf(r.text)
    res = s.post(f"{chartink.BASE}/screener/process", data={"scan_clause": CLAUSE, "column_clause": cols},
                 headers={"X-CSRF-TOKEN": token, "X-Requested-With": "XMLHttpRequest",
                          "Referer": f"{chartink.BASE}/screener"}, timeout=90)
    res.raise_for_status()
    j = res.json()
    if j.get("scan_error"):
        raise RuntimeError(f"Chartink: {j['scan_error']}")
    return j.get("data") or []


# ---------- റിസൾട്ട് തീയതി log ----------

def update_log(today):
    """data/events.json-ലെ (NSE) തീയതികൾ log-ൽ ചേർക്കും. തിരികെ: {SYMBOL: [YYYY-MM-DD, ...]}."""
    try:
        log = json.loads(LOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log = {}
    try:
        ev = json.loads(EVENTS.read_text(encoding="utf-8")).get("results", {})
    except (OSError, ValueError):
        ev = {}
    for sym, d in ev.items():
        lst = log.setdefault(sym.upper(), [])
        if d not in lst:
            lst.append(d)
            lst.sort()
    cutoff = (today - timedelta(days=400)).isoformat()  # പഴയവ ഒഴിവാക്കും
    log = {k: [d for d in v if d >= cutoff] for k, v in log.items()}
    log = {k: v for k, v in log.items() if v}
    LOG.write_text(json.dumps(log, indent=0, sort_keys=True), encoding="utf-8")
    return log


# ---------- ട്രേഡിംഗ് ദിവസങ്ങൾ ----------

def trading_dates(bdata, today, include_today=True):
    """GM World-ലെ സെഷൻ തീയതികൾ (+ ഇന്ന്, മാർക്കറ്റ് അടച്ച ശേഷമാണെങ്കിൽ) → ['YYYY-MM-DD', ...] പഴയത് ആദ്യം."""
    out = []
    if bdata and bdata.get("dates") and bdata.get("asOf"):
        last = datetime.strptime(bdata["asOf"], "%d %b %Y").date()
        for s in bdata["dates"]:
            d = datetime.strptime(f"{s} {last.year}", "%d %b %Y").date()
            if d > last:
                d = d.replace(year=last.year - 1)
            out.append(d)
        out.sort()
    if include_today and (not out or out[-1] < today) and today.weekday() < 5:
        out.append(today)
    if not out:
        d = today
        while d.weekday() >= 5 or (d == today and not include_today):
            d -= timedelta(days=1)
        out.append(d)
    if len(out) < N + 2:  # GM World ഇല്ലെങ്കിൽ: ആഴ്ചാവസാനം ഒഴിവാക്കിയുള്ള ദിവസങ്ങൾ (അവധി ദിവസങ്ങൾ കണക്കിലില്ല)
        d = out[0]
        while len(out) < N + 2:
            d -= timedelta(days=1)
            if d.weekday() < 5:
                out.insert(0, d)
    return [d.isoformat() for d in out]


# ---------- Excellent result ----------

def _growth(a, b):
    if a is None or b is None or b <= 0:
        return None
    return (a / b - 1) * 100


def _core(d, q):
    pbt, oi = d.get(f"pbt{q}"), d.get(f"oi{q}")
    return None if pbt is None or oi is None else pbt - oi


def _margin(d, q):
    core, i, dp, ns = _core(d, q), d.get(f"in{q}"), d.get(f"dp{q}"), d.get(f"ns{q}")
    if None in (core, i, dp) or not ns:
        return None
    return (core + i + dp) / ns * 100


def sue(d):
    """(Δ0 − mean(Δ1..Δ8)) / std(Δ1..Δ8),  Δq = profit(q) − profit(q+4). പുതിയ കമ്പനികൾക്ക് കുറഞ്ഞത് 4 മുൻ Δ."""
    np_ = [d.get(f"np{i}") for i in range(13)]
    deltas = []
    for q in range(9):
        if np_[q] is None or np_[q + 4] is None:
            break
        deltas.append(np_[q] - np_[q + 4])
    if len(deltas) < 5:  # കുറഞ്ഞത് 4 മുൻ ക്വാർട്ടർ മാറ്റം വേണം
        return None
    hist = deltas[1:]
    m = sum(hist) / len(hist)
    sd = (sum((x - m) ** 2 for x in hist) / (len(hist) - 1)) ** 0.5
    return round((deltas[0] - m) / sd, 1) if sd > 0 else None


def score(d):
    """7 പരിശോധന → (excellent?, പാസായ എണ്ണം, [(label, ok, note)])"""
    c = CFG
    np_ = [d.get(f"np{i}") for i in range(6)]
    g0, g1 = _growth(np_[0], np_[4]), _growth(np_[1], np_[5])
    gs = _growth(d.get("ns0"), d.get("ns4"))
    gc = _growth(_core(d, 0), _core(d, 4))
    oi_share = (d["oi0"] / d["pbt0"] * 100) if (d.get("oi0") is not None and d.get("pbt0")) else None
    checks = [
        ("EPS growth", g0 is not None and g0 >= c["eps_min"], f"Profit YoY {g0:+.0f}%" if g0 is not None else "മുൻ വർഷം നഷ്ടം"),
        ("Sales growth", gs is not None and gs >= c["sales_min"], f"Sales YoY {gs:+.0f}%" if gs is not None else "ഡാറ്റ ഇല്ല"),
        ("Quality of earnings", gc is not None and gc >= c["core_min"],
         (f"Core profit (PBT − other income) YoY {gc:+.0f}%" if gc is not None else "Core profit താരതമ്യം ഇല്ല")
         + (f" · other income PBT-യുടെ {oi_share:.0f}%" if oi_share is not None else "")),
        ("Acceleration", g0 is not None and g1 is not None and g0 > g1,
         f"{g0:+.0f}% vs മുൻ Q {g1:+.0f}%" if (g0 is not None and g1 is not None) else "മുൻ Q താരതമ്യം ഇല്ല"),
        ("QoQ growth", None not in np_[:2] and np_[0] > np_[1], "Profit മുൻ ക്വാർട്ടറിനേക്കാൾ കൂടുതൽ" if (None not in np_[:2] and np_[0] > np_[1]) else "മുൻ ക്വാർട്ടറിനേക്കാൾ കുറവ്"),
        ("Record quarter", None not in np_[:5] and np_[0] >= max(np_[:5]), "5 ക്വാർട്ടറിലെ ഉയർന്ന profit" if (None not in np_[:5] and np_[0] >= max(np_[:5])) else "റെക്കോർഡ് അല്ല"),
        ("Real growth", np_[4] is not None and np_[4] > 0, "ഒരു വർഷം മുമ്പും ലാഭം" if (np_[4] or 0) > 0 else "low base (മുൻ വർഷം നഷ്ടം)"),
    ]
    n = sum(1 for _, ok, _ in checks if ok)
    return checks[0][1] and checks[1][1] and checks[2][1] and n >= c["need"], n, checks


def labels(d, dates, rd):
    """SUE, മാർക്കറ്റ് പ്രതികരണം, margin, base effect — Excellent തീരുമാനിക്കുന്നതിൽ ഇല്ല."""
    c = CFG
    out = {"sue": sue(d)}
    idx = next((i for i, x in enumerate(dates) if x >= rd), None)
    best = None
    for j in ((idx, idx + 1) if idx is not None else ()):
        k = len(dates) - 1 - j
        if j > len(dates) - 1 or k >= N:
            continue
        ck, cp = d.get(f"c{k}"), d.get(f"c{k + 1}")
        if not ck or not cp:
            continue
        chg = (ck / cp - 1) * 100
        volx = (d.get(f"v{k}") or 0) / d["av50"] if d.get("av50") else None
        if best is None or chg > best[1]:
            best = (dates[j], chg, volx)
    if best:
        out["react_date"], out["react"], out["volx"] = best[0], round(best[1], 1), round(best[2], 1) if best[2] else None
        out["react_ok"] = best[1] >= c["react_min"] and (best[2] or 0) >= c["vol_min"]
    m0, m4 = _margin(d, 0), _margin(d, 4)
    if m0 is not None and m4 is not None:
        out["margin"], out["margin_prev"] = round(m0, 1), round(m4, 1)
    g0 = _growth(d.get("np0"), d.get("np4"))
    out["base_effect"] = g0 is not None and g0 >= c["base_warn"]
    return out


# ---------- ട്രാക്കർ ----------

def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"active": [], "done": []}


def _series_from(d, dates):
    """Chartink c0..cN → {date: close}"""
    out = {}
    for k in range(N + 1):
        if k < len(dates) and d.get(f"c{k}") is not None:
            out[dates[-1 - k]] = d[f"c{k}"]
    return out


def run(now, bdata, sectors=None, fetch_fn=fetch, save=True):
    """ട്രാക്കർ പുതുക്കും (now = IST datetime). പേജിനുള്ള dict തിരികെ."""
    today = now.date()
    log = update_log(today)
    dates = trading_dates(bdata, today, include_today=now.hour >= 16)  # 4 PM-ന് മുമ്പ് ഇന്നത്തെ candle ഇല്ല
    today_s = dates[-1]
    data = fetch_fn()
    print(f"  PEAD: Chartink {len(data)} സ്റ്റോക്ക്, റിസൾട്ട് log {len(log)} കമ്പനി")
    st = load_state()
    active = {e["symbol"]: e for e in st["active"]}
    try:
        seen = json.loads(SEEN.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        seen = {}
    added = []
    first = dates[max(0, len(dates) - CFG["add_window"])]
    for sym, d in data.items():
        rds = [x for x in log.get(sym, []) if first <= x <= today_s]
        if not rds or sym in active:
            continue
        rd = rds[-1]
        if any(e["symbol"] == sym and e["res_date"] == rd for e in st["done"]):
            continue
        # Chartink പുതിയ ക്വാർട്ടർ ചേർത്തോ? റിസൾട്ടിന് മുമ്പ് രേഖപ്പെടുത്തിയ profit-ൽ നിന്ന് മാറിയാൽ മാത്രം.
        prior = [v for dt, v in seen.get(sym, []) if dt < rd]
        if prior:
            if d.get("np0") is not None and abs(prior[-1] - d["np0"]) < 1e-6:
                continue  # ഇനിയും പഴയ ക്വാർട്ടർ — നാളെ വീണ്ടും നോക്കും
        elif rd >= today_s:
            continue  # മുൻ രേഖ ഇല്ല, റിസൾട്ട് ഇന്ന് — ഒരു ദിവസം കാത്തിരിക്കും
        ok, n, checks = score(d)
        if not ok:
            continue
        before = [x for x in dates if x < rd]
        series = _series_from(d, dates)
        if not before or before[-1] not in series:
            continue
        e = {"symbol": sym, "name": d.get("name", ""), "sector": (sectors or {}).get(sym, ""), "res_date": rd,
             "base_date": before[-1], "base": series[before[-1]], "score": n,
             "checks": [[lab, ok_, note] for lab, ok_, note in checks], "added": today_s, **labels(d, dates, rd),
             "series": {k: v for k, v in series.items() if k > before[-1]}}
        active[sym] = e
        added.append(sym)
    # ദിവസേനയുള്ള വില ചേർക്കൽ
    from lib import chartink
    done_now = []
    for sym, e in list(active.items()):
        d = data.get(sym)
        if d:
            for k, v in _series_from(d, dates).items():
                if k > e["base_date"]:
                    e["series"][k] = v
            if len(e["series"]) <= 3:  # പ്രതികരണ ദിവസം പൂർത്തിയാകുന്നത് വരെ ലേബലുകൾ പുതുക്കും
                e.update(labels(d, dates, e["res_date"]))
        elif sym in chartink.INDICATORS and chartink.INDICATORS[sym].get("close"):
            e["series"][today_s] = chartink.INDICATORS[sym]["close"]
        e["series"] = dict(sorted(e["series"].items()))
        if len(e["series"]) >= CFG["track_days"]:
            done_now.append(sym)
    # ഇന്നത്തെ profit രേഖപ്പെടുത്തൽ (മാറ്റം വന്നാൽ മാത്രം, അവസാന 4 എണ്ണം)
    for sym, d in data.items():
        if d.get("np0") is None:
            continue
        h = seen.setdefault(sym, [])
        if not h or abs(h[-1][1] - d["np0"]) >= 1e-6:
            h.append([today_s, d["np0"]])
            seen[sym] = h[-4:]
    if save:
        SEEN.write_text(json.dumps(seen, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    for sym in done_now:
        st["done"].append(active.pop(sym))
    st["active"] = sorted(active.values(), key=lambda e: e["res_date"], reverse=True)
    st["done"] = st["done"][-200:]
    if save:
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"  PEAD: ട്രാക്കിൽ {len(st['active'])}, ഇന്ന് പുതിയത് {len(added)} ({', '.join(added[:10])})")
    return {"date": today_s, "active": st["active"], "done": st["done"][-30:], "added": added, "cfg": CFG}


def telegram_line(res):
    if not res:
        return ""
    s = f"PEAD: ട്രാക്കിൽ {len(res['active'])}"
    if res["added"]:
        s += " · ഇന്ന് Excellent റിസൾട്ട്: " + ", ".join(res["added"][:8])
    best = []
    for e in res["active"]:
        if e["series"]:
            last = list(e["series"].values())[-1]
            best.append((last / e["base"] - 1) * 100 if e["base"] else 0)
    if best:
        top = sorted(((((list(e["series"].values())[-1] / e["base"] - 1) * 100), e["symbol"]) for e in res["active"] if e["series"] and e["base"]), reverse=True)[:3]
        s += " · മുന്നിൽ: " + ", ".join(f"{sym} {p:+.0f}%" for p, sym in top)
    return s
