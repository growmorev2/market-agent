"""സ്റ്റോക്ക് സെലക്ഷൻ strategy: രണ്ട് portfolio (Momentum, Value).

ഓരോ ദിവസവും:
  1. സ്കാനർ റിസൾട്ടുകളിൽ നിന്ന് candidates എടുക്കും
       Momentum = GM Universe ∩ Top MSWING (ആദ്യ 100 റാങ്ക്)
       Value    = ROE/EPS IMPROVING
  2. Yahoo Finance-ൽ നിന്ന് 1 വർഷത്തെ വില എടുത്ത് 20 EMA / 50 DMA / 200 DMA കണക്കാക്കും
  3. ഓരോ സ്റ്റോക്കിനും ഫിൽറ്ററുകൾ (noise കുറയ്ക്കാൻ) → Buy ready / Watch
  4. ഒരു model portfolio (data/strategy.json) സൂക്ഷിക്കും: exit നിയമം വന്നവ പുറത്ത്,
     Market status അനുവദിക്കുന്ന അത്രയും പുതിയ Buy ready സ്റ്റോക്കുകൾ അകത്ത്

Value portfolio-ക്കുള്ള intrinsic value (Gangil's 3) data/valuations.json-ൽ നിന്ന് വായിക്കും:
    {"SYMBOL": 1234.5, ...}   അല്ലെങ്കിൽ   {"SYMBOL": {"intrinsic": 1234.5}, ...}
ഫയൽ ഇല്ലെങ്കിൽ valuation ഫിൽറ്റർ ഒഴിവാക്കും (പേജിൽ "valuation pending" എന്ന് കാണിക്കും).

അക്കങ്ങൾ മാറ്റാൻ താഴെയുള്ള CFG / GATE നോക്കുക. ഇത് സാമ്പത്തിക ഉപദേശമല്ല.
"""
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STATE = DATA / "strategy.json"
VALUATIONS = DATA / "valuations.json"
HISTORY = DATA / "history"
IST = timezone(timedelta(hours=5, minutes=30))

CFG = {
    "momentum": {"max_pos": 10, "stop": 0.10, "extended": 0.15, "persist_need": 3, "persist_of": 5,
                 "rank_window": 100, "out_days": 3, "below50_days": 2},
    "value": {"max_pos": 10, "mos": 0.20, "below200": 0.10, "out_days": 3, "near200": 0.20,
              "persist_need": 3, "persist_of": 5},
}
# Market status → പരമാവധി എത്ര പൊസിഷൻ (ഇല്ലെങ്കിൽ max_pos). 0 = പുതിയ entry ഇല്ല.
GATE = {
    "momentum": {"Stay out": 0, "Failed turn": 0, "Wait": 0, "Bottoming": 3, "Early rally": 3},
    "value": {"Stay out": 0},
}
SLUG_MSWING, SLUG_UNIVERSE, SLUG_VALUE = "top-mswing", "gm-universe", "eps-improving-4"

# niftyindices Industry → GM World Landry sector key
NI_TO_LANDRY = {
    "Information Technology": "i.t", "Fast Moving Consumer Goods": "fmcg", "Healthcare": "healthcare",
    "Financial Services": "financials", "Realty": "realty", "Chemicals": "chemicals", "Textiles": "textiles",
    "Construction Materials": "building materials", "Automobile and Auto Components": "auto",
    "Metals & Mining": "metals & mining", "Capital Goods": "industrials", "Construction": "industrials",
    "Consumer Durables": "consumer discretionary", "Consumer Services": "consumer discretionary",
    "Media, Entertainment & Publication": "media", "Services": "services",
    "Oil Gas & Consumable Fuels": "energy", "Power": "power & utilities", "Telecommunication": "telecom",
    "Diversified": "miscellaneous", "Forest Materials": "miscellaneous",
}
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


# ---------- വില, indicators ----------

def price_history(symbols, sleep=0.25):
    """{symbol: [(date, close), ...]} — Yahoo Finance, 1 വർഷം. കിട്ടാത്തവ ഒഴിവാക്കും."""
    out, s = {}, requests.Session()
    for sym in sorted(set(symbols)):
        try:
            r = s.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}.NS",
                      params={"range": "1y", "interval": "1d"}, headers=HEADERS, timeout=30)
            res = r.json()["chart"]["result"][0]
            rows = [(datetime.fromtimestamp(t, IST).date(), float(c))
                    for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"]) if c is not None]
            if rows:
                out[sym] = rows
        except Exception:  # noqa: BLE001
            pass
        time.sleep(sleep)
    return out


def _sma(v, n):
    return sum(v[-n:]) / n if len(v) >= n else None


def _ema(v, n):
    if len(v) < n:
        return None
    e = sum(v[:n]) / n
    k = 2 / (n + 1)
    for x in v[n:]:
        e = x * k + e * (1 - k)
    return e


def indicators(rows, close_today=None):
    """close (ഇന്നത്തെ സ്കാനർ ക്ലോസിന് മുൻഗണന), ema20, sma50, sma200, prev close/sma50."""
    if not rows:
        return None
    closes = [c for _, c in rows]
    if close_today:
        closes[-1] = close_today
    return {"close": closes[-1], "ema20": _ema(closes, 20), "sma50": _sma(closes, 50), "sma200": _sma(closes, 200),
            "prev_close": closes[-2] if len(closes) > 1 else None,
            "prev_sma50": _sma(closes[:-1], 50) if len(closes) > 50 else None}


# ---------- ഹിസ്റ്ററി (persistence, out-days) ----------

def _scan(scans, slug):
    return next((s for s in scans if s.get("slug") == slug and not s.get("error")), None)


def _ranks(scan):
    return (scan or {}).get("ranks") or (scan or {}).get("_ranks") or {}


def past_days(date_str, n):
    """ഇന്നേക്ക് മുമ്പുള്ള n ദിവസത്തെ history (പഴയത് ആദ്യം)."""
    files = sorted(p for p in HISTORY.glob("*.json") if p.stem < date_str)[-n:]
    out = []
    for p in files:
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except ValueError:
            pass
    return out


def membership(days, today_scans, slug, use_ranks=False, window=100):
    """ഓരോ ദിവസവും (പഴയത് ആദ്യം, ഇന്ന് അവസാനം) ആ സ്കാനറിലെ സ്റ്റോക്കുകളുടെ set."""
    out = []
    for d in [*days, {"scans": today_scans}]:
        s = _scan(d.get("scans") or [], slug)
        if s is None:
            out.append(None)  # ആ ദിവസം ഡാറ്റ ഇല്ല/പിശക് — കണക്കിൽ എടുക്കില്ല
        elif use_ranks:
            out.append({k for k, r in _ranks(s).items() if r <= window})
        else:
            out.append({x["symbol"] for x in s["stocks"]})
    return out


def _consecutive_out(sym, sets, n):
    known = [st for st in sets if st is not None][-n:]
    return len(known) >= n and all(sym not in st for st in known)


# ---------- സെക്ടർ ----------

def strong_sectors(bdata):
    """Landry momentum-ൽ മുകളിലെ പകുതിയിലുള്ള സെക്ടറുകൾ (keys). ഡാറ്റ ഇല്ലെങ്കിൽ None."""
    sec = (bdata or {}).get("sectors") or {}
    vals = sorted(((k, v[-1]) for k, v in sec.items() if v and k not in ("n/a", "indices")), key=lambda x: -x[1])
    if not vals:
        return None
    return {k for k, _ in vals[: (len(vals) + 1) // 2]}


# ---------- ഫിൽറ്ററുകൾ ----------

def _f(key, label, ok, note=""):
    return {"k": key, "label": label, "ok": ok, "note": note}


def momentum_filters(sym, ind, persist, results, sector, strong):
    c = CFG["momentum"]
    f = [_f("persist", "Stable rank", persist >= c["persist_need"],
            f"{persist}/{c['persist_of']} ദിവസം Top {c['rank_window']}-ൽ")]
    if ind and ind["sma50"] and ind["sma200"]:
        ok = ind["close"] > ind["sma50"] > ind["sma200"]
        f.append(_f("trend", "Trend", ok, "Close > 50 DMA > 200 DMA" if ok else "Close/50/200 ക്രമം ശരിയല്ല"))
    else:
        f.append(_f("trend", "Trend", False, "വില ഡാറ്റ കിട്ടിയില്ല"))
    if ind and ind["ema20"]:
        ext = ind["close"] / ind["ema20"] - 1
        f.append(_f("ext", "Not extended", ext <= c["extended"], f"20 EMA-യിൽ നിന്ന് {ext * 100:+.0f}%"))
    else:
        f.append(_f("ext", "Not extended", False, "വില ഡാറ്റ കിട്ടിയില്ല"))
    f.append(_f("results", "No results soon", sym not in results,
                f"റിസൾട്ട് {results[sym]}" if sym in results else "7 ദിവസത്തിൽ ഇല്ല"))
    key = NI_TO_LANDRY.get(sector or "")
    if strong is None or not key:
        f.append(_f("sector", "Strong sector", True, "സെക്ടർ ഡാറ്റ ഇല്ല — ഒഴിവാക്കി"))
    else:
        f.append(_f("sector", "Strong sector", key in strong, sector))
    return f


def value_filters(sym, ind, intrinsic, have_val, persist):
    c = CFG["value"]
    f = [_f("persist", "Stable in scanner", persist >= c["persist_need"],
            f"{persist}/{c['persist_of']} ദിവസം ROE/EPS സ്കാനറിൽ")]
    if have_val:
        if intrinsic:
            mos = 1 - ind["close"] / intrinsic if ind else None
            f.append(_f("mos", "Margin of safety", mos is not None and mos >= c["mos"],
                        f"Intrinsic {intrinsic:,.0f} · {mos * 100:.0f}% താഴെ" if mos is not None else "വില ഇല്ല"))
        else:
            f.append(_f("mos", "Margin of safety", False, "ഈ സ്റ്റോക്കിന് valuation ഇല്ല"))
    if ind and ind["sma200"]:
        prem = ind["close"] / ind["sma200"] - 1
        f.append(_f("above200", "Above 200 DMA", prem > 0, f"200 DMA-യിൽ നിന്ന് {prem * 100:+.0f}%"))
        f.append(_f("near200", "Near 200 DMA", prem <= c["near200"],
                    f"{int(c['near200'] * 100)}%-നുള്ളിൽ" if prem <= c["near200"] else f"{prem * 100:.0f}% മുകളിൽ — pullback-ന് കാത്തിരിക്കുക"))
    else:
        f.append(_f("above200", "Above 200 DMA", False, "വില ഡാറ്റ കിട്ടിയില്ല"))
        f.append(_f("near200", "Near 200 DMA", False, "വില ഡാറ്റ കിട്ടിയില്ല"))
    return f


def status_of(filters):
    fails = sum(1 for x in filters if not x["ok"])
    return "buy" if fails == 0 else "watch" if fails <= 2 else "reject"


# ---------- model portfolio ----------

def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"momentum": {"open": [], "closed": []}, "value": {"open": [], "closed": []}}


def load_valuations():
    try:
        raw = json.loads(VALUATIONS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    out = {}
    for k, v in raw.items():
        val = v.get("intrinsic") if isinstance(v, dict) else v
        try:
            out[k.upper()] = float(val)
        except (TypeError, ValueError):
            pass
    return out


def _close_pos(pos, date_str, price, reason):
    ret = (price / pos["entry"] - 1) * 100 if pos["entry"] else None
    return {**pos, "exit_date": date_str, "exit": round(price, 2), "ret": round(ret, 2) if ret is not None else None,
            "reason": reason}


def run(date_str, scans, results, bdata, mstatus, sample=False, fetch=price_history):
    """മുഴുവൻ strategy ഓടിക്കും; state സേവ് ചെയ്യും (sample-ൽ ഇല്ല). പേജിനുള്ള dict തിരികെ."""
    state = load_state()
    valuations = load_valuations()
    have_val = bool(valuations)
    cm, cv = CFG["momentum"], CFG["value"]
    days = [] if sample else past_days(date_str, max(cm["persist_of"], cm["out_days"], cv["out_days"]) - 1)

    ms_scan, uni_scan, val_scan = _scan(scans, SLUG_MSWING), _scan(scans, SLUG_UNIVERSE), _scan(scans, SLUG_VALUE)
    ranks_today = _ranks(ms_scan)
    rank_sets = membership(days, scans, SLUG_MSWING, use_ranks=True, window=cm["rank_window"])
    val_sets = membership(days, scans, SLUG_VALUE)
    info = {x["symbol"]: x for s in scans for x in s.get("stocks", [])}

    m_cands = sorted({x["symbol"] for x in (uni_scan or {}).get("stocks", [])}
                     & {k for k, r in ranks_today.items() if r <= cm["rank_window"]})
    v_cands = sorted({x["symbol"] for x in (val_scan or {}).get("stocks", [])})
    held = [p["symbol"] for pf in ("momentum", "value") for p in state[pf]["open"]]
    print(f"  Strategy: Momentum {len(m_cands)}, Value {len(v_cands)}, കൈവശം {len(held)} — വില എടുക്കുന്നു…")
    hist = fetch(set(m_cands) | set(v_cands) | set(held))
    print(f"  വില കിട്ടിയത്: {len(hist)} സ്റ്റോക്ക്")
    ind = {s: indicators(hist.get(s), (info.get(s) or {}).get("close")) for s in set(m_cands) | set(v_cands) | set(held)}
    strong = strong_sectors(bdata)
    status_name = (mstatus or {}).get("name")

    # --- Momentum ---
    m_rows = []
    window_sets = [st for st in rank_sets if st is not None][-cm["persist_of"]:]
    for sym in m_cands:
        persist = sum(1 for st in window_sets if sym in st)
        x = info.get(sym, {})
        flt = momentum_filters(sym, ind.get(sym), persist, results, x.get("sector"), strong)
        m_rows.append({"symbol": sym, "sector": x.get("sector", ""), "close": (ind.get(sym) or {}).get("close") or x.get("close"),
                       "rank": ranks_today.get(sym), "filters": flt, "status": status_of(flt)})
    m_rows.sort(key=lambda r: (r["rank"] or 999))

    # --- Value ---
    v_rows = []
    vwin = [st for st in val_sets if st is not None][-cv["persist_of"]:]
    for sym in v_cands:
        x, i = info.get(sym, {}), ind.get(sym)
        intrinsic = (valuations or {}).get(sym)
        flt = value_filters(sym, i, intrinsic, have_val, sum(1 for st in vwin if sym in st))
        prem = (i["close"] / i["sma200"] - 1) if (i and i["sma200"]) else None
        mos = (1 - i["close"] / intrinsic) if (i and intrinsic) else None
        v_rows.append({"symbol": sym, "sector": x.get("sector", ""), "close": (i or {}).get("close") or x.get("close"),
                       "intrinsic": intrinsic, "mos": mos, "prem200": prem, "filters": flt, "status": status_of(flt)})
    v_rows.sort(key=lambda r: (-(r["mos"] if r["mos"] is not None else -9), r["prem200"] if r["prem200"] is not None else 9))

    # --- Exits ---
    exits = {"momentum": [], "value": []}
    for pf in ("momentum", "value"):
        keep = []
        for p in state[pf]["open"]:
            i = ind.get(p["symbol"])
            reason = None
            if i:
                p["last"] = round(i["close"], 2)
                if pf == "momentum":
                    if i["close"] <= p["entry"] * (1 - cm["stop"]):
                        reason = f"Stop-loss {int(cm['stop'] * 100)}%"
                    elif i["sma50"] and i["prev_sma50"] and i["close"] < i["sma50"] and i["prev_close"] < i["prev_sma50"]:
                        reason = "50 DMA-ക്ക് താഴെ 2 ദിവസം"
                    elif _consecutive_out(p["symbol"], rank_sets, cm["out_days"]):
                        reason = f"{cm['out_days']} ദിവസമായി MSWING Top {cm['rank_window']}-ൽ ഇല്ല"
                else:
                    intrinsic = (valuations or {}).get(p["symbol"])
                    if intrinsic and i["close"] >= intrinsic:
                        reason = "Intrinsic value എത്തി"
                    elif i["sma200"] and i["close"] < i["sma200"] * (1 - cv["below200"]):
                        reason = f"200 DMA-ക്ക് {int(cv['below200'] * 100)}%-ൽ കൂടുതൽ താഴെ"
                    elif _consecutive_out(p["symbol"], val_sets, cv["out_days"]):
                        reason = f"{cv['out_days']} ദിവസമായി ROE/EPS സ്കാനറിൽ ഇല്ല"
            if reason:
                c = _close_pos(p, date_str, i["close"], reason)
                state[pf]["closed"].append(c)
                exits[pf].append(c)
            else:
                keep.append(p)
        state[pf]["open"] = keep

    # --- Entries ---
    entries = {"momentum": [], "value": []}
    caps = {}
    for pf, rows in (("momentum", m_rows), ("value", v_rows)):
        cap = GATE[pf].get(status_name, CFG[pf]["max_pos"]) if status_name else CFG[pf]["max_pos"]
        caps[pf] = cap
        open_syms = {p["symbol"] for p in state[pf]["open"]}
        just_exited = {c["symbol"] for c in exits[pf]}
        for r in rows:
            if len(state[pf]["open"]) >= cap:
                break
            if r["status"] == "buy" and r["symbol"] not in open_syms | just_exited and r["close"]:
                p = {"symbol": r["symbol"], "sector": r["sector"], "entry_date": date_str,
                     "entry": round(r["close"], 2), "last": round(r["close"], 2)}
                state[pf]["open"].append(p)
                entries[pf].append(p)
                open_syms.add(r["symbol"])

    if not sample:
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    held_now = {pf: {p["symbol"] for p in state[pf]["open"]} for pf in state}
    for pf, rows in (("momentum", m_rows), ("value", v_rows)):
        for r in rows:
            r["held"] = r["symbol"] in held_now[pf]
    return {
        "date": date_str, "mstatus": mstatus, "caps": caps, "max_pos": {k: CFG[k]["max_pos"] for k in CFG},
        "have_val": have_val, "prices": len(hist),
        "momentum": {"rows": m_rows, "open": state["momentum"]["open"], "closed": state["momentum"]["closed"][-30:],
                     "exits": exits["momentum"], "entries": entries["momentum"]},
        "value": {"rows": [r for r in v_rows if r["status"] != "reject"] or v_rows[:40],
                  "total": len(v_rows), "open": state["value"]["open"], "closed": state["value"]["closed"][-30:],
                  "exits": exits["value"], "entries": entries["value"]},
    }


def telegram_line(res):
    """റിപ്പോർട്ടിലെ ഒറ്റ വരി സംഗ്രഹം."""
    if not res:
        return ""
    bits = []
    for pf, name in (("momentum", "Momentum"), ("value", "Value")):
        d = res[pf]
        buy = sum(1 for r in d["rows"] if r["status"] == "buy")
        s = f"{name}: Buy ready {buy} · കൈവശം {len(d['open'])}"
        if d["entries"]:
            s += " · പുതിയത് " + ", ".join(p["symbol"] for p in d["entries"])
        if d["exits"]:
            s += " · Exit " + ", ".join(p["symbol"] for p in d["exits"])
        bits.append(s)
    return "\n".join(bits)
