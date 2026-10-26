"""ദിവസേനയുള്ള ക്ലോസിംഗ് വിലകൾ എടുക്കുന്ന ഭാഗം (പെർഫോമൻസ് ട്രാക്കറിന്).

1. NSE bhavcopy — ഒരു ദിവസത്തെ മുഴുവൻ മാർക്കറ്റിന്റെയും ക്ലോസിംഗ് വില ഒറ്റ CSV-യിൽ.
   വൈകിട്ട് ~6 മണിയോടെയാണ് പ്രസിദ്ധീകരിക്കുന്നത്; അതുകൊണ്ട് ഇന്നത്തേത് കിട്ടിയില്ലെങ്കിൽ
   നാളത്തെ റണ്ണിൽ എടുക്കും (ഒരു ദിവസവും നഷ്ടപ്പെടില്ല).
2. NSE തടഞ്ഞാൽ: Yahoo Finance (ഓരോ സ്റ്റോക്കിനും വേറെ request).
"""
import csv
import io
import time
from datetime import date, datetime, timedelta, timezone

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "*/*",
}
BHAV = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{d:%d%m%Y}.csv"
SERIES_PREF = ("EQ", "BE", "BZ", "SM", "ST")


class Blocked(RuntimeError):
    pass


def parse_bhavcopy(text):
    rows = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    best = {}
    for row in rows:
        row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        sym, series = row.get("SYMBOL"), row.get("SERIES")
        if not sym or series not in SERIES_PREF:
            continue
        try:
            close = float(row.get("CLOSE_PRICE", ""))
        except ValueError:
            continue
        rank = SERIES_PREF.index(series)
        if sym not in best or rank < best[sym][0]:
            best[sym] = (rank, close)
    return {k: v[1] for k, v in best.items()}


def bhavcopy(d, session=None):
    """ആ ദിവസം ട്രേഡിംഗ് ഇല്ലെങ്കിൽ / ഇതുവരെ ഇറങ്ങിയില്ലെങ്കിൽ None. NSE തടഞ്ഞാൽ Blocked."""
    s = session or requests
    try:
        r = s.get(BHAV.format(d=d), headers=HEADERS, timeout=30)
    except requests.RequestException as e:
        raise Blocked(str(e)) from e
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise Blocked(f"HTTP {r.status_code}")
    data = parse_bhavcopy(r.text)
    return data or None


def yahoo_history(symbols, after, until):
    """{date: {symbol: close}} — after-ന് ശേഷം until വരെയുള്ള ദിവസങ്ങൾ."""
    out = {}
    for sym in symbols:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}.NS"
        try:
            r = requests.get(url, params={"range": "3mo", "interval": "1d"}, headers=HEADERS, timeout=30)
            res = r.json()["chart"]["result"][0]
            ts = res["timestamp"]
            closes = res["indicators"]["quote"][0]["close"]
        except Exception:  # noqa: BLE001
            continue
        for t, c in zip(ts, closes):
            if c is None:
                continue
            d = datetime.fromtimestamp(t, timezone(timedelta(hours=5, minutes=30))).date()
            if after < d <= until:
                out.setdefault(d, {})[sym] = round(float(c), 2)
        time.sleep(0.3)
    return out


def closes_since(last_date, today, symbols, max_days=15):
    """last_date-ന് ശേഷമുള്ള എല്ലാ ട്രേഡിംഗ് ദിവസങ്ങളുടെയും ക്ലോസ്: {date: {symbol: close}}, ഉറവിടം."""
    start = max(last_date + timedelta(days=1), today - timedelta(days=max_days))
    out, d = {}, start
    session = requests.Session()
    try:
        while d <= today:
            if d.weekday() < 5:
                data = bhavcopy(d, session)
                if data:
                    out[d] = data
            d += timedelta(days=1)
        return out, "NSE bhavcopy"
    except Blocked:
        if not symbols:
            return {}, "none"
        return yahoo_history(sorted(symbols), start - timedelta(days=1), today), "Yahoo Finance"
