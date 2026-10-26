"""സ്കാനർ പെർഫോമൻസ് ട്രാക്കർ.

ഒരു സ്റ്റോക്ക് ഒരു സ്കാനറിൽ പുതുതായി വരുന്ന ദിവസത്തെ ക്ലോസിംഗ് വില "എൻട്രി" ആയി സേവ് ചെയ്യും.
തുടർന്നുള്ള 20 ട്രേഡിംഗ് ദിവസത്തെ ക്ലോസ് രേഖപ്പെടുത്തും (സ്കാനറിൽ നിന്ന് പോയാലും).
അതിൽ നിന്ന് ഓരോ സ്കാനറിനും: 5 / 10 / 20 ദിവസത്തിന് ശേഷം ശരാശരി റിട്ടേൺ, എത്ര % ലാഭത്തിൽ.

ഇത് ഒരു കണക്ക് മാത്രമാണ് (ബ്രോക്കറേജ്, സ്ലിപ്പേജ്, സ്റ്റോപ്പ് ലോസ് ഒന്നും ഇല്ല) —
ഏത് സ്കാനർ നന്നായി പ്രവർത്തിക്കുന്നു എന്ന് താരതമ്യം ചെയ്യാനുള്ളത്.
ഫയൽ: data/tracker.json
"""
import json
import statistics
from datetime import date
from pathlib import Path

from lib import prices

FILE = Path(__file__).resolve().parent.parent / "data" / "tracker.json"
HORIZONS = (5, 10, 20)
WINDOW = max(HORIZONS)


def load():
    if FILE.exists():
        return json.loads(FILE.read_text(encoding="utf-8"))
    return {"last_price_date": None, "entries": []}


def save(state):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def open_entries(state):
    return [e for e in state["entries"] if not e["done"]]


def apply_closes(state, closes_by_date):
    """{date: {symbol: close}} — തീയതി ക്രമത്തിൽ ഓരോ തുറന്ന എൻട്രിയിലും ചേർക്കും."""
    for d in sorted(closes_by_date):
        ds = d.isoformat()
        day = closes_by_date[d]
        for e in open_entries(state):
            if e["date"] < ds and e["symbol"] in day and (not e["closes"] or e["closes"][-1][0] < ds):
                e["closes"].append([ds, day[e["symbol"]]])
                if len(e["closes"]) >= WINDOW:
                    e["done"] = True
        if not state["last_price_date"] or ds > state["last_price_date"]:
            state["last_price_date"] = ds


def update_prices(state, today):
    """കഴിഞ്ഞ റണ്ണിന് ശേഷമുള്ള ക്ലോസിംഗ് വിലകൾ ചേർക്കും. തിരികെ: ഉറവിടം, എത്ര ദിവസം."""
    if not open_entries(state):
        return "—", 0
    last = date.fromisoformat(state["last_price_date"] or min(e["date"] for e in open_entries(state)))
    symbols = {e["symbol"] for e in open_entries(state)}
    closes, source = prices.closes_since(last, today, symbols)
    apply_closes(state, closes)
    return source, len(closes)


def add_entries(state, date_str, scans, regime=None):
    """ഇന്ന് പുതുതായി വന്ന സ്റ്റോക്കുകൾ എൻട്രി ആയി ചേർക്കും (അതേ സ്കാനറിൽ തുറന്ന എൻട്രി ഇല്ലെങ്കിൽ)."""
    if state["last_price_date"] is None:
        state["last_price_date"] = date_str
    active = {(e["scan"], e["symbol"]) for e in open_entries(state)}
    added = 0
    for s in scans:
        by_sym = {x["symbol"]: x for x in s["stocks"]}
        for sym in s.get("new", []):
            x = by_sym.get(sym)
            if not x or not x.get("close") or (s["slug"], sym) in active:
                continue
            state["entries"].append({
                "scan": s["slug"], "scan_name": s["name"], "symbol": sym,
                "sector": x.get("sector", "Unknown"), "date": date_str, "entry": x["close"],
                "closes": [], "done": False, "regime": regime,
            })
            added += 1
    return added


def _ret(e, n):
    if len(e["closes"]) < n or not e["entry"]:
        return None
    return (e["closes"][n - 1][1] / e["entry"] - 1) * 100


def stats(state):
    """ഓരോ സ്കാനറിനും 5/10/20 ദിവസത്തെ കണക്ക്."""
    groups = {}
    for e in state["entries"]:
        groups.setdefault(e["scan"], {"name": e["scan_name"], "entries": []})["entries"].append(e)
    out = []
    for slug, g in groups.items():
        row = {"slug": slug, "name": g["name"], "total": len(g["entries"]),
               "open": sum(1 for e in g["entries"] if not e["done"]), "h": {}}
        for n in HORIZONS:
            rets = [r for r in (_ret(e, n) for e in g["entries"]) if r is not None]
            row["h"][n] = None if not rets else {
                "n": len(rets),
                "avg": round(statistics.mean(rets), 2),
                "median": round(statistics.median(rets), 2),
                "win": round(sum(r > 0 for r in rets) / len(rets) * 100),
            }
        row["regime"] = {}
        for lvl in ("green", "yellow", "red"):
            rets = [r for r in (_ret(e, 10) for e in g["entries"] if e.get("regime") == lvl) if r is not None]
            if rets:
                row["regime"][lvl] = {"n": len(rets), "avg": round(statistics.mean(rets), 2),
                                      "win": round(sum(r > 0 for r in rets) / len(rets) * 100)}
        done = [(e, _ret(e, WINDOW)) for e in g["entries"] if _ret(e, WINDOW) is not None]
        done.sort(key=lambda t: -t[1])
        row["best"] = [(e["symbol"], e["date"], round(r, 1)) for e, r in done[:3]]
        row["worst"] = [(e["symbol"], e["date"], round(r, 1)) for e, r in done[-3:][::-1]] if len(done) > 3 else []
        out.append(row)
    out.sort(key=lambda r: r["name"])
    return out


def stats_text(rows):
    """AI-ക്കും ആഴ്ച റാപ്പപ്പിനും കൊടുക്കാനുള്ള ചുരുക്കം."""
    lines = []
    for r in rows:
        parts = []
        for n in HORIZONS:
            h = r["h"][n]
            parts.append(f"{n}d: n={h['n']}, avg {h['avg']}%, median {h['median']}%, win {h['win']}%" if h else f"{n}d: not enough data yet")
        reg = "; ".join(f"{k} market: n={v['n']}, avg {v['avg']}%, win {v['win']}%" for k, v in r.get("regime", {}).items())
        lines.append(f"- {r['name']} ({r['total']} entries, {r['open']} still tracking): " + "; ".join(parts)
                     + (f" | 10d by market condition: {reg}" if reg else ""))
    return "\n".join(lines) or "No tracked entries yet."
