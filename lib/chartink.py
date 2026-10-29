"""Chartink-ൽ നിന്ന് സ്കാനർ റിസൾട്ട് എടുക്കുന്ന ഭാഗം.

ഓരോ സ്കാനറിനും:
  - scans.json-ൽ "clause" ഉണ്ടെങ്കിൽ (ശുപാർശ): /screener പേജിൽ നിന്ന് CSRF token മാത്രം എടുത്ത്
    ആ clause നേരിട്ട് അയക്കും — നിങ്ങളുടെ chartink_scan.py ചെയ്യുന്ന അതേ രീതി. അപ്പോൾ "slug" ഒരു പേര് മാത്രം.
  - "clause" ഇല്ലെങ്കിൽ: സ്കാനർ പേജ് (screener/<slug>) തുറന്ന് clause കണ്ടെത്താൻ ശ്രമിക്കും.
  - തുടർന്ന് /screener/process-ലേക്ക് clause അയച്ച് റിസൾട്ട് (JSON) വാങ്ങും
"""
import html
import json
import re

import requests

BASE = "https://chartink.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def new_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _csrf(page):
    m = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', page)
    return m.group(1) if m else None


def _scan_clause(page):
    """പേജിനുള്ളിൽ scan clause പല രൂപത്തിൽ കാണാം; ഓരോന്നും ശ്രമിക്കും."""
    m = re.search(r'<textarea[^>]*name="scan_clause"[^>]*>(.*?)</textarea>', page, re.S)
    if m and m.group(1).strip():
        return html.unescape(m.group(1)).strip()
    text = html.unescape(page)
    for pat in (r'"scan_clause"\s*:\s*"((?:\\.|[^"\\])*)"',
                r"scan_clause\s*:\s*'((?:\\.|[^'\\])*)'"):
        m = re.search(pat, text)
        if m and m.group(1).strip():
            try:
                return json.loads('"' + m.group(1) + '"').strip()
            except ValueError:
                return m.group(1).strip()
    return None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# Strategy-ക്കുള്ള moving averages Chartink തന്നെ കണക്കാക്കും (Yahoo GitHub-ൽ നിന്ന് തടയുന്നു).
# scans.json-ൽ "indicators": true ഉള്ള സ്കാനറുകളിലെ എല്ലാ സ്റ്റോക്കുകളുടെയും മൂല്യം ഇവിടെ ശേഖരിക്കും.
IND_COLS = {"ind-c": "Daily Close", "ind-e20": "Daily Ema( Close , 20 )", "ind-s50": "Daily Sma( Close , 50 )",
            "ind-s200": "Daily Sma( Close , 200 )", "ind-pc": "1 day ago Close", "ind-ps50": "1 day ago Sma( Close , 50 )"}
IND_KEYS = {"ind-c": "close", "ind-e20": "ema20", "ind-s50": "sma50", "ind-s200": "sma200",
            "ind-pc": "prev_close", "ind-ps50": "prev_sma50"}
DEFAULT_COLS = (" Daily Close as 'scan-column-default-close',  Daily \"close - 1 candle ago close / 1 candle ago close * 100\""
                " as 'scan-column-default-percent-change',  Daily Volume as 'scan-column-default-volume'")
INDICATORS = {}


def run_scan(session, scan):
    """scan = {"name":..., "slug":..., "clause": (optional)} → സ്റ്റോക്ക് ലിസ്റ്റ്"""
    clause = (scan.get("clause") or "").strip()
    if clause:
        url = f"{BASE}/screener"
        token = getattr(session, "_ck_token", None)
        if not token:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            token = _csrf(r.text)
            session._ck_token = token
    else:
        url = f"{BASE}/screener/{scan['slug']}"
        r = session.get(url, timeout=30)
        r.raise_for_status()
        token = _csrf(r.text)
        clause = _scan_clause(r.text)
    if not token:
        raise RuntimeError("CSRF token കിട്ടിയില്ല (Chartink പേജ് മാറിയിരിക്കാം)")
    if not clause:
        raise RuntimeError(
            "scan clause കണ്ടെത്താനായില്ല. scans.json-ൽ ഈ സ്കാനറിന് \"clause\" നേരിട്ട് ചേർക്കുക."
        )
    data = {"scan_clause": clause}
    cols = scan.get("columns") or ""
    if scan.get("indicators"):
        cols = (cols or DEFAULT_COLS) + "," + ",".join(f" {v} as '{k}'" for k, v in IND_COLS.items())
    if cols:
        data["column_clause"] = cols
    res = session.post(
        f"{BASE}/screener/process",
        data=data,
        headers={"X-CSRF-TOKEN": token, "X-Requested-With": "XMLHttpRequest", "Referer": url},
        timeout=60,
    )
    res.raise_for_status()
    rows = res.json().get("data", []) or []
    stocks = []
    for row in rows:
        sym = row.get("nsecode") or row.get("bsecode")
        if not sym:
            continue
        item = {
            "symbol": str(sym),
            "name": row.get("name", ""),
            "close": _num(row.get("close", row.get("scan-column-default-close"))),
            "change": _num(row.get("per_chg", row.get("scan-column-default-percent-change"))),
            "volume": _num(row.get("volume", row.get("scan-column-default-volume"))),
        }
        if scan.get("score_col"):
            item["score"] = _num(row.get(scan["score_col"]))
        if scan.get("indicators"):
            ind = {IND_KEYS[k]: _num(row.get(k)) for k in IND_COLS}
            if ind["close"] is not None:
                INDICATORS[str(sym)] = ind
        stocks.append(item)
    if scan.get("score_col"):
        return rank(stocks, scan)
    return stocks


def rank(stocks, scan):
    """സ്കോർ അനുസരിച്ച് ഉയർന്നതിൽ നിന്ന് റാങ്ക് ചെയ്യും. stocks = Top N മാത്രം;
    rank_window വരെയുള്ള റാങ്കുകൾ scan["_ranks"]-ൽ (നാളെ റാങ്ക് മാറ്റം കണക്കാക്കാൻ)."""
    good = sorted((x for x in stocks if x.get("score") is not None), key=lambda x: -x["score"])
    for i, x in enumerate(good, 1):
        x["rank"] = i
    scan["_ranks"] = {x["symbol"]: x["rank"] for x in good[: scan.get("rank_window", 100)]}
    return good[: scan.get("top", 20)]
