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
    res = session.post(
        f"{BASE}/screener/process",
        data={"scan_clause": clause},
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
        stocks.append({
            "symbol": str(sym),
            "name": row.get("name", ""),
            "close": _num(row.get("close")),
            "change": _num(row.get("per_chg")),
            "volume": _num(row.get("volume")),
        })
    return stocks
