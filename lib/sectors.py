"""ഓരോ സ്റ്റോക്കിന്റെയും സെക്ടർ (Industry) കണ്ടെത്തുന്ന ഭാഗം.

Chartink റിസൾട്ടിൽ സെക്ടർ ഇല്ല. അതുകൊണ്ട് NSE (niftyindices.com) പ്രസിദ്ധീകരിക്കുന്ന
ഇൻഡക്സ് ലിസ്റ്റുകളിൽ നിന്ന് Symbol → Industry പട്ടിക ഉണ്ടാക്കി data/sectors.csv-ൽ സേവ് ചെയ്യും.
30 ദിവസത്തിലൊരിക്കൽ പുതുക്കും. ഡൗൺലോഡ് പരാജയപ്പെട്ടാൽ പഴയ പട്ടിക തന്നെ ഉപയോഗിക്കും.

പട്ടികയിൽ ഇല്ലാത്ത ചെറിയ സ്റ്റോക്കുകൾക്ക്: data/sector_overrides.csv-ൽ
    SYMBOL,Industry
എന്ന രീതിയിൽ സ്വയം ചേർക്കാം (ഇതിന് മുൻഗണനയുണ്ട്).
"""
import csv
import io
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent.parent / "data"
CACHE = DATA / "sectors.csv"
META = DATA / "sectors_meta.json"
OVERRIDES = DATA / "sector_overrides.csv"
UNKNOWN = "Unknown"

SOURCES = [
    "https://www.niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv",
    "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv",
    "https://www.niftyindices.com/IndexConstituent/ind_niftymicrocap250_list.csv",
]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/csv,*/*",
}


def _read_csv(text):
    out = {}
    for row in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        sym, ind = row.get("symbol"), row.get("industry")
        if sym and ind:
            out[sym.upper()] = ind
    return out


def _download():
    merged = {}
    for url in SOURCES:
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                for k, v in _read_csv(r.text).items():
                    merged.setdefault(k, v)
        except requests.RequestException:
            pass
    return merged


def _stale(days):
    try:
        updated = date.fromisoformat(json.loads(META.read_text())["updated"])
        return date.today() - updated > timedelta(days=days)
    except (OSError, ValueError, KeyError):
        return True


def load(refresh_days=30, allow_download=True):
    mapping = {}
    if CACHE.exists():
        mapping = _read_csv(CACHE.read_text(encoding="utf-8"))
    if allow_download and (not mapping or _stale(refresh_days)):
        fresh = _download()
        if len(fresh) > 200:  # പകുതി വഴി പരാജയപ്പെട്ട ഡൗൺലോഡ് പഴയതിനെ മാറ്റില്ല
            mapping = fresh
            DATA.mkdir(exist_ok=True)
            with CACHE.open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["Symbol", "Industry"])
                w.writerows(sorted(mapping.items()))
            META.write_text(json.dumps({"updated": date.today().isoformat(), "count": len(mapping)}))
    if OVERRIDES.exists():
        for line in OVERRIDES.read_text(encoding="utf-8").splitlines():
            if "," in line and not line.lower().startswith("symbol"):
                sym, ind = line.split(",", 1)
                if sym.strip() and ind.strip():
                    mapping[sym.strip().upper()] = ind.strip()
    return mapping


def tag(scans, mapping):
    for s in scans:
        for x in s["stocks"]:
            x["sector"] = mapping.get(x["symbol"].upper()) or x.get("sector") or UNKNOWN


def summary(scans):
    """എല്ലാ സ്കാനറുകളും ചേർത്ത് സെക്ടർ തിരിച്ചുള്ള എണ്ണം (ഒരു സ്റ്റോക്ക് ഒരിക്കൽ മാത്രം)."""
    seen, new_syms = {}, set()
    for s in scans:
        new_syms.update(s.get("new", []))
        for x in s["stocks"]:
            seen.setdefault(x["symbol"], x.get("sector", UNKNOWN))
    total = Counter(seen.values())
    new = Counter(seen[sym] for sym in new_syms if sym in seen)
    rows = [{"sector": k, "count": v, "new": new.get(k, 0),
             "stocks": sorted(sym for sym, sec in seen.items() if sec == k)}
            for k, v in total.items()]
    rows.sort(key=lambda r: (r["sector"] == UNKNOWN, -r["count"], r["sector"]))
    return rows
