"""
Chartink scanner (multiple scans) -> sorted -> top N -> separate TradingView list per scan
Run:  python tv/chartink_scan.py   (GitHub Actions: .github/workflows/tv-watchlist.yml, 7:07 PM IST തിങ്കൾ–വെള്ളി)

Env vars (GitHub Secrets):
  TV_SESSIONID, TV_SESSIONID_SIGN   -> TradingView login cookies (നിർബന്ധം)
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID -> പ്രശ്നമുണ്ടായാൽ അലേർട്ട്
  TV_LIST_ID    -> optional, list for scan 1 (default 350461598 MSWING, replaced each run)
  TV_LIST_ID_2  -> optional, list for scan 2 (default 342469658 GM Universe, replaced each run)
  TV_LIST_ID_3  -> optional, list for holygrail (default 351125833 "3️⃣HOLYGRAIL", new stocks added)
  TV_LIST_ID_4  -> optional, list for multibagger (default 351126063 "4️⃣MULTIBAGGER", new stocks added)
  TV_LIST_ID_5  -> optional, list for eps_improving (default 352386514 "EPS IMPROVING", replaced each run)
"""
import os
from datetime import date

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE = "https://chartink.com"
OUT_DIR = "watchlists"

SCANS = [
    {
        "name": "my_scan",
        "list_env": "TV_LIST_ID",
        "default_list_id": "350461598",  # MSWING
        "clause": r"""( {166311} not(  1 > 0 ) ) and( {cash} (  market cap >=  500 and  daily sma(  daily volume , 10 ) >=  1000 and  daily sma(  daily volume , 10 ) *  daily sma(  daily close , 10 ) >=  10000000 and  daily ^12017('output'='val')^ >  1 ) )""",
        "columns": (
            " Daily ^12017('output'='val')^ as 'scan-column-_3d483', "
            " Daily Close as 'scan-column-default-close'"
        ),
        "sort_col": "scan-column-_3d483",
        "descending": True,
        "top_n": 1000,
    },
    {
        "name": "gm_universe",
        "list_env": "TV_LIST_ID_2",
        "default_list_id": "342469658",  # GM Universe
        "clause": r'''( {cash} (  market cap >  200 and  daily sma(  daily volume , 10 ) *  daily sma(  daily close , 10 ) >=  100000000 and  daily {custom_indicator_162248_start}"{custom_indicator_162246_start} "(  close - 20 candles ago close ) * 100 / 20"{custom_indicator_162246_end} +  {custom_indicator_162247_start} "(  close - 50 candles ago close ) * 100 / ( 50 candles ago close * 50 )"{custom_indicator_162247_end}"{custom_indicator_162248_end} >  0 and  daily {custom_indicator_162248_start}"{custom_indicator_162246_start} "(  close - 20 candles ago close ) * 100 / 20"{custom_indicator_162246_end} +  {custom_indicator_162247_start} "(  close - 50 candles ago close ) * 100 / ( 50 candles ago close * 50 )"{custom_indicator_162247_end}"{custom_indicator_162248_end} >=  daily ema(  daily {custom_indicator_162248_start}"{custom_indicator_162246_start} "(  close - 20 candles ago close ) * 100 / 20"{custom_indicator_162246_end} +  {custom_indicator_162247_start} "(  close - 50 candles ago close ) * 100 / ( 50 candles ago close * 50 )"{custom_indicator_162247_end}"{custom_indicator_162248_end} , 9 ) and  daily wma(  daily rsi( 9 ) , 20 ) >=  45 ) )''',
        "columns": r""" Daily Close as 'scan-column-default-close',  Daily "close - 1 candle ago close / 1 candle ago close * 100" as 'scan-column-default-percent-change', filternumber( daily close >  1 day ago close,1) as 'default-percent-change-conditional-filters-color',  Daily Volume as 'scan-column-default-volume'""",
        "sort_col": "scan-column-default-percent-change",  # % change, highest first
        "descending": True,
        "top_n": 1000,
    },
    {
        # chartink.com/screener/gm-signal ("7. GM HOLLYGRAIL LONG TERM")
        "name": "holygrail",
        "list_env": "TV_LIST_ID_3",
        "default_list_id": "351125833",  # 3️⃣HOLYGRAIL
        "mode": "append",  # only add new stocks, never remove
        "clause": r"""( {cash} (  (  daily open +  daily close +  daily high +  daily low ) >  (  1 day ago open +  1 day ago close +  1 day ago high +  1 day ago low ) and(  1 day ago open +  1 day ago close +  1 day ago high +  1 day ago low ) >  (  2 days ago open +  2 days ago close +  2 days ago high +  2 days ago low ) and  daily high >  1 day ago high and  1 day ago high >  2 days ago high and  daily sma( volume,100 ) >  100000 and  daily close >  1 and  daily close <  1200 and  daily ema( close,20 ) >  daily ema( close,60 ) and  daily rsi( 14 ) >=  60 and  market cap >  500 and  daily sma(  daily volume , 10 ) *  daily sma(  daily close , 10 ) >=  10000000 ) )""",
        "columns": r""" Daily Close as 'scan-column-default-close',  Daily "close - 1 candle ago close / 1 candle ago close * 100" as 'scan-column-default-percent-change', filternumber( daily close >  1 day ago close,1) as 'default-percent-change-conditional-filters-color',  Daily Volume as 'scan-column-default-volume'""",
        "sort_col": None,
        "descending": True,
        "top_n": 1000,
    },
    {
        # chartink.com/screener/copy-momentum-portfolio-original-scan-by-hitesh-1319 ("MULTIBAGGER 100%")
        "name": "multibagger",
        "list_env": "TV_LIST_ID_4",
        "default_list_id": "351126063",  # 4️⃣MULTIBAGGER
        "mode": "append",  # only add new stocks, never remove
        "clause": r"""( {cash} (  weekly close >  1 week ago max( 52 ,  weekly close ) and  1 week ago close <  2 weeks ago max( 52 ,  weekly close ) and  2 weeks ago close <  3 weeks ago max( 52 ,  weekly close ) and  3 weeks ago close <  4 weeks ago max( 52 ,  weekly close ) and  4 weeks ago close <  5 weeks ago max( 52 ,  weekly close ) and  5 weeks ago close <  6 weeks ago max( 52 ,  weekly close ) and  market cap >=  500 and  weekly sma(  weekly close *  weekly volume , 4 ) >  250000000 ) )""",
        "columns": r""" Daily Close as 'scan-column-default-close',  Daily "close - 1 candle ago close / 1 candle ago close * 100" as 'scan-column-default-percent-change', filternumber( daily close >  1 day ago close,1) as 'default-percent-change-conditional-filters-color',  Daily Volume as 'scan-column-default-volume',  Market Cap as 'scan-column-_ebd34'""",
        "sort_col": None,
        "descending": True,
        "top_n": 1000,
    },
    {
        # chartink.com/screener/eps-improving-4 (shown on Chartink as "ROE IMPROVING")
        "name": "eps_improving",
        "list_env": "TV_LIST_ID_5",
        "default_list_id": "352386514",  # EPS IMPROVING
        # no "mode": list is fully replaced each run
        "clause": r"""( {cash} (  quarterly net profit/reported profit after tax >  4 quarters ago net profit/reported profit after tax and  2 quarter ago net profit/reported profit after tax >  5 quarters ago net profit/reported profit after tax and  3 quarter ago net profit/reported profit after tax >  6 quarters ago net profit/reported profit after tax and  quarterly net profit/reported profit after tax >  4 quarters ago net profit/reported profit after tax *  1.2 and  quarterly net sales >  4 quarters ago net sales *  1.1 and  market cap >  500 ) )""",
        "columns": r""" Daily Close as 'scan-column-default-close',  Daily "close - 1 candle ago close / 1 candle ago close * 100" as 'scan-column-default-percent-change', filternumber( daily close >  1 day ago close,1) as 'default-percent-change-conditional-filters-color',  Daily Volume as 'scan-column-default-volume'""",
        "sort_col": None,
        "descending": True,
        "top_n": 1000,
    },
]


def list_id_for(scan):
    return os.environ.get(scan["list_env"]) or scan.get("default_list_id")


def run_scan(session, clause, columns):
    page = session.get(f"{BASE}/screener", timeout=30)
    soup = BeautifulSoup(page.text, "html.parser")
    token = soup.find("meta", {"name": "csrf-token"})["content"]
    resp = session.post(
        f"{BASE}/screener/process",
        data={"scan_clause": clause, "column_clause": columns},
        headers={"X-CSRF-TOKEN": token, "Referer": f"{BASE}/screener"},
        timeout=60,
    )
    resp.raise_for_status()
    return pd.DataFrame(resp.json().get("data", []))


def sort_df(df, col, descending):
    if col is None:
        return df
    print("  Columns returned:", list(df.columns))
    if col not in df.columns:
        print(f"  WARNING: sort column '{col}' not found, keeping Chartink's order.")
        return df
    df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.sort_values(col, ascending=not descending, na_position="last")
    print("  Top 3:", list(zip(df["nsecode"].head(3), df[col].head(3))))
    return df


def tv_symbol(s):
    return "NSE:" + s.replace("&", "_").replace("-", "_")


def push_to_tradingview(list_id, symbols):
    """UNOFFICIAL. Replaces the whole contents of that TradingView list."""
    sid = os.environ.get("TV_SESSIONID")
    sign = os.environ.get("TV_SESSIONID_SIGN")
    if not (sid and sign and list_id):
        print("  TradingView env vars not set; skipping push.")
        return
    r = requests.post(
        f"https://www.tradingview.com/api/v1/symbols_list/custom/{list_id}/replace/?unsafe=true",
        json=[tv_symbol(s) for s in symbols],
        cookies={"sessionid": sid, "sessionid_sign": sign},
        headers={
            "Origin": "https://www.tradingview.com",
            "Referer": "https://www.tradingview.com/",
            "User-Agent": "Mozilla/5.0",
        },
        timeout=30,
    )
    print(f"  TradingView push to list {list_id}:", r.status_code, r.text[:80])
    STATUS.setdefault("tv", {})[str(list_id)] = r.status_code
    if r.status_code != 200:
        ISSUES.append(f"TradingView list {list_id}: HTTP {r.status_code} {r.text[:60]}")


STATUS = {}  # tv/last_run.json — ഓരോ റണ്ണിന്റെയും ചുരുക്കം (secrets ഇല്ല)
ISSUES = []  # ഈ റണ്ണിലെ പ്രശ്നങ്ങൾ — അവസാനം Telegram-ലേക്ക് (env.sh-ൽ TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID ഉണ്ടെങ്കിൽ)


def alert_telegram(lines):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print("  (Telegram alert: env.sh-ൽ TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID ഇല്ല — skip)")
        return
    text = "⚠️ TradingView watchlist (GitHub) — പ്രശ്നം\n\n" + "\n".join("• " + x for x in lines)
    if any("401" in x or "403" in x for x in lines):
        text += "\n\nTradingView login കാലഹരണപ്പെട്ടിരിക്കാം — GitHub Secrets-ൽ TV_SESSIONID, TV_SESSIONID_SIGN പുതുക്കുക."
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat, "text": text[:4000]}, timeout=30)
        print("  Telegram alert അയച്ചു")
    except Exception as e:
        print(f"  Telegram alert പരാജയം: {e}")


TV_HEADERS = {
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
    "User-Agent": "Mozilla/5.0",
}


def _read_symbols(path):
    """Read NSE:XXX symbols from a file (one per line or comma separated). Missing file -> empty set."""
    if not os.path.exists(path):
        return set()
    out = set()
    for part in open(path).read().replace(",", "\n").splitlines():
        part = part.strip()
        if not part or part.startswith("#"):
            continue
        out.add(part if ":" in part else tv_symbol(part))
    return out


def append_to_tradingview(list_id, symbols, scan_name=None):
    """UNOFFICIAL. Adds stocks to that TradingView list; never removes any.

    Keeps a record of every stock that belongs in the list (added_<scan>.txt). Each run it also
    puts back any recorded stock that has disappeared from the list (for example when TradingView
    saved an old copy of the list over the script's additions).
    Stocks you want permanently out of the list go in skip_<scan>.txt (one per line, e.g. NSE:ABC or ABC).
    """
    sid = os.environ.get("TV_SESSIONID")
    sign = os.environ.get("TV_SESSIONID_SIGN")
    if not (sid and sign and list_id):
        print("  TradingView env vars not set; skipping push.")
        return
    cookies = {"sessionid": sid, "sessionid_sign": sign}
    r = requests.get("https://www.tradingview.com/api/v1/symbols_list/all/",
                     cookies=cookies, headers=TV_HEADERS, timeout=30)
    if r.status_code != 200:
        print(f"  TradingView read failed for list {list_id}:", r.status_code, r.text[:80])
        ISSUES.append(f"TradingView list {list_id} വായിക്കാനായില്ല: HTTP {r.status_code}")
        return
    current = next((l for l in r.json() if str(l.get("id")) == str(list_id)), None)
    if current is None:
        print(f"  ERROR: TradingView list {list_id} not found; nothing added.")
        ISSUES.append(f"TradingView list {list_id} കണ്ടെത്തിയില്ല")
        return
    name = current.get("name", list_id)
    have_list = list(current.get("symbols") or [])
    have = set(have_list)
    today_syms = list(dict.fromkeys(tv_symbol(x) for x in symbols))

    ledger_path = f"added_{scan_name}.txt" if scan_name else None
    skip = _read_symbols(f"skip_{scan_name}.txt") if scan_name else set()
    if ledger_path and not os.path.exists(ledger_path):
        # First run with the record: start from what is in the list right now.
        with open(ledger_path, "w") as f:
            f.write("\n".join(have_list) + ("\n" if have_list else ""))
        print(f"  Started record {ledger_path} with the {len(have_list)} stocks now in {name}")
    recorded = _read_symbols(ledger_path) if ledger_path else set()

    new = [s for s in today_syms if s not in have and s not in skip]
    restore = sorted(s for s in recorded if s not in have and s not in skip and s not in new)

    if ledger_path:
        missing_from_record = [s for s in today_syms if s not in recorded]
        if missing_from_record:
            with open(ledger_path, "a") as f:
                f.write("\n".join(missing_from_record) + "\n")

    to_add = new + restore
    if not to_add:
        print(f"  TradingView list {name}: nothing new to add ({len(have)} stocks)")
        return
    r = requests.post(
        f"https://www.tradingview.com/api/v1/symbols_list/custom/{list_id}/append/",
        json=to_add, cookies=cookies, headers=TV_HEADERS, timeout=30,
    )
    if r.status_code != 200:
        ISSUES.append(f"TradingView add to {name}: HTTP {r.status_code} {r.text[:60]}")
    STATUS.setdefault("tv", {})[str(list_id)] = r.status_code
    msg = f"  TradingView add to {name}: {r.status_code}, +{len(new)} new"
    if new:
        msg += " -> " + ", ".join(s[4:] for s in new)[:300]
    if restore:
        msg += f" | put back {len(restore)} that had gone missing -> " + ", ".join(s[4:] for s in restore)[:300]
    print(msg)


def main():
    from datetime import datetime
    os.chdir(os.path.dirname(os.path.abspath(__file__)))  # added_*.txt / skip_*.txt ഈ ഫോൾഡറിൽ
    if not (os.environ.get("TV_SESSIONID") and os.environ.get("TV_SESSIONID_SIGN")):
        print("TV_SESSIONID / TV_SESSIONID_SIGN secrets ഇല്ല — Chartink മാത്രം ഓടിക്കും, TradingView-ലേക്ക് അയക്കില്ല.")
    print(f"===== Run {datetime.now():%Y-%m-%d %H:%M} =====")
    os.makedirs(OUT_DIR, exist_ok=True)
    today = date.today().isoformat()

    # Safety: two scans must never point at the same TradingView list
    ids = [list_id_for(s) for s in SCANS]
    if len(set(ids)) != len(ids) or not all(ids):
        print("ERROR: each scan needs its own, different TV list id:", ids)
        alert_telegram([f"TradingView list id-കളിൽ പ്രശ്നം: {ids}"])
        return

    for scan in SCANS:
        print(f"{scan['name']}:")
        try:
            session = requests.Session()
            session.headers["User-Agent"] = "Mozilla/5.0"
            df = run_scan(session, scan["clause"], scan["columns"])
            print(f"  {len(df)} stocks")
            STATUS.setdefault("scans", {})[scan["name"]] = len(df)
            if df.empty:
                print("  No stocks, list left unchanged.")
                continue
            df = sort_df(df, scan["sort_col"], scan["descending"])
            df.to_csv(f"{OUT_DIR}/{today}_{scan['name']}.csv", index=False)
            symbols = list(dict.fromkeys(df["nsecode"].tolist()))[: scan["top_n"]]
            with open(f"{OUT_DIR}/{today}_{scan['name']}_tradingview.txt", "w") as f:
                f.write(",".join(tv_symbol(s) for s in symbols))
            print(f"  Final: {len(symbols)} symbols")
            if scan.get("mode") == "append":
                append_to_tradingview(list_id_for(scan), symbols, scan["name"])
            else:
                push_to_tradingview(list_id_for(scan), symbols)
        except Exception as e:
            print(f"  ERROR in {scan['name']}: {e}")
            ISSUES.append(f"{scan['name']}: {str(e)[:150]}")
    import json
    STATUS.update({"run": datetime.now().strftime("%Y-%m-%d %H:%M"), "issues": ISSUES,
                   "tv_login": bool(os.environ.get("TV_SESSIONID") and os.environ.get("TV_SESSIONID_SIGN"))})
    with open("last_run.json", "w") as f:
        json.dump(STATUS, f, ensure_ascii=False, indent=1)
    if ISSUES:
        alert_telegram(ISSUES)


if __name__ == "__main__":
    main()
