"""ആഴ്ചയിലെ ദിവസേനയുള്ള ഹിസ്റ്ററി ഫയലുകൾ ചേർത്ത് ഒരു ആഴ്ച ചുരുക്കം ഉണ്ടാക്കുന്ന ഭാഗം."""
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

UNKNOWN = "Unknown"


def load_week(history_dir, end_day, days=7):
    """end_day ഉൾപ്പെടെ കഴിഞ്ഞ `days` ദിവസത്തെ ഹിസ്റ്ററി ഫയലുകൾ (പഴയത് ആദ്യം)."""
    start = end_day - timedelta(days=days - 1)
    out = []
    for p in sorted(Path(history_dir).glob("*.json")):
        try:
            d = date.fromisoformat(p.stem)
        except ValueError:
            continue
        if start <= d <= end_day:
            out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def _pct(a, b):
    if a in (None, 0) or b is None:
        return None
    return round((b / a - 1) * 100, 2)


def aggregate(week):
    dates = [h["date"] for h in week]
    by_slug = {}
    sector_days = Counter()
    sector_first, sector_last = Counter(), Counter()
    sector_of = {}

    for i, h in enumerate(week):
        day_syms = {}
        for s in h["scans"]:
            e = by_slug.setdefault(s["slug"], {
                "name": s["name"], "slug": s["slug"], "daily": {}, "days_in": Counter(),
                "first": {}, "last": {}, "sets": {},
            })
            if s.get("error"):
                e["daily"][h["date"]] = None
                continue
            syms = set()
            for x in s["stocks"]:
                sym = x["symbol"]
                syms.add(sym)
                e["days_in"][sym] += 1
                e["first"].setdefault(sym, x.get("close"))
                e["last"][sym] = x.get("close")
                sector_of[sym] = x.get("sector", UNKNOWN)
                day_syms[sym] = sector_of[sym]
            e["daily"][h["date"]] = len(syms)
            e["sets"][h["date"]] = syms
        for sym, sec in day_syms.items():
            sector_days[sec] += 1
        if i == 0:
            sector_first = Counter(day_syms.values())
        if i == len(week) - 1:
            sector_last = Counter(day_syms.values())

    scans = []
    for e in by_slug.values():
        ok_days = [d for d in dates if e["daily"].get(d) is not None]
        first_set = e["sets"].get(ok_days[0], set()) if ok_days else set()
        last_set = e["sets"].get(ok_days[-1], set()) if ok_days else set()
        all_week = sorted(sym for sym, n in e["days_in"].items() if ok_days and n == len(ok_days))
        movers = []
        for sym, n in e["days_in"].items():
            if n >= 2:
                movers.append({"symbol": sym, "days": n, "sector": sector_of.get(sym, UNKNOWN),
                               "week_change": _pct(e["first"].get(sym), e["last"].get(sym))})
        movers.sort(key=lambda m: -(m["week_change"] if m["week_change"] is not None else -999))
        scans.append({
            "name": e["name"], "slug": e["slug"],
            "daily": [(d, e["daily"].get(d)) for d in dates],
            "unique": len(e["days_in"]),
            "entered": sorted(last_set - first_set),
            "exited": sorted(first_set - last_set),
            "all_week": all_week,
            "movers": movers[:15],
        })

    sectors = []
    for sec in set(sector_days) | set(sector_first) | set(sector_last):
        sectors.append({"sector": sec, "stock_days": sector_days[sec],
                        "first": sector_first.get(sec, 0), "last": sector_last.get(sec, 0)})
    sectors.sort(key=lambda r: (r["sector"] == UNKNOWN, -r["stock_days"], r["sector"]))
    return {"dates": dates, "scans": scans, "sectors": sectors}
