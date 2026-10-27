"""മാർക്കറ്റ് ഏജന്റ് — പ്രധാന ഫയൽ.

ദിവസേന (python agent.py):
  1. scans.json-ലെ ഓരോ Chartink സ്കാനറും ഓടിക്കും
  2. ഓരോ സ്റ്റോക്കിനും സെക്ടർ ചേർക്കും, ഇന്നലത്തേതുമായി താരതമ്യം ചെയ്യും
  3. ഡാറ്റ AI-ക്ക് കൊടുത്ത് വിശകലന റിപ്പോർട്ട് എഴുതിക്കും (Gemini → Groq)
  4. വെബ്‌പേജ് ഉണ്ടാക്കും (GitHub Pages)
  5. Telegram-ലേക്കും Discord-ലേക്കും അയക്കും

ആഴ്ചയിൽ (python agent.py --weekly):
  കഴിഞ്ഞ 7 ദിവസത്തെ ഹിസ്റ്ററി ചേർത്ത് ആഴ്ച റാപ്പപ്പ് ഉണ്ടാക്കി അയക്കും

പരീക്ഷിക്കാൻ:  python agent.py --sample --no-ai --no-send
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lib import ai, breadth, chartink, events, notify, pdf, report, sectors, site, tracker, weekly

ROOT = Path(__file__).parent
HISTORY = ROOT / "data" / "history"
IST = timezone(timedelta(hours=5, minutes=30))

RULES = """Rules:
- Use only the data given (and news you actually find, when you have a search tool). Do not invent prices, news, results or facts.
- Never tell the trader to buy or sell anything. Describe and highlight; decisions are theirs.
- Sector "Unknown" means the sector could not be looked up; do not treat it as a real sector.
- Keep stock symbols and sector names in English.
- Call a stock "new" only if it is listed under "New today". If yesterday is "unknown (first run)",
  this is the first run and new-entry comparison starts from the next report."""

FORMAT_WEEKLY = """
- Use short bullet points ("- ") under short headings ("## "). Write the headings in the report language."""

SYSTEM_DAILY = """You are a market analyst assistant for an Indian (NSE) swing trader.
You receive today's results from the trader's own Chartink scanners (with each stock's sector)
and the market breadth from the trader's own GM World dashboard.
The report layout is built by code. Your job is only the short summary and the reasons.
Return ONLY one JSON object and nothing else, in exactly this shape:
{{"summary": "...", "reasons": {{"SYMBOL": "..."}}, "sectors": {{"Sector name": "..."}}}}
- summary: 2-3 short, plain sentences in {lang}. What the breadth says about the market, what
  today's scans show, and how the two relate. Descriptive only. No lists, no headings, no symbols
  like # or *.
- reasons: keys are the stocks under "Explain these stocks"; value is ONE short line in {lang}.
- sectors: keys are the sectors under "Explain these sectors"; value is ONE short line in {lang}.
""" + RULES

DRIVERS_DAILY = """
You have a web search tool. Fill "reasons" and "sectors" from recent news you actually find
(last few days; Indian market sources): the most likely driver of the move, in ONE short line in
{lang}. If nothing clear, write "വ്യക്തമായ വാർത്തയില്ല". Never guess or make up a reason.
No links, no URLs, no source names.
"""

DRIVERS_WEEKLY = """
You have a web search tool. In the sector rotation and persistent-stocks sections, add the
likely driver behind each move in ONE short line, based on news you actually find from this
week (Indian market sources). If nothing clear, say no clear news was found. Never guess.
Give the reason only: no links, no URLs, no source names.
"""

NO_DRIVERS = """
Do not explain why stocks or sectors moved; you have no news access today.
If the output format has "reasons" and "sectors" fields, return them as empty objects.
"""

SYSTEM_WEEKLY = """You are a market analyst assistant for an Indian (NSE) swing trader.
You receive a summary of one week of results from the trader's own Chartink scanners, and the
market breadth from the trader's own GM World dashboard.
Write a weekly wrap-up in {lang}.
Structure:
0. Market condition through the week: how the breadth numbers moved session by session and
   where the market stands now (descriptive only)
1. The week in 3-4 lines: how the scanner counts moved through the week (broadening or narrowing)
2. Most persistent stocks: in the scanners most days, with their change over the week
3. Sector rotation: sectors gaining presence vs losing presence from start to end of week
4. Notable entries and exits during the week
5. Scanner performance so far (from "Scanner performance"): compare how each scanner's new
   entries did after 5/10/20 trading days, and by market condition (green/yellow/red) when that
   data exists. Always mention the sample size (n); if n is small (under 20), say clearly it is
   too early to judge.
6. Things to keep an eye on next week (descriptive observations only, not advice)
Under 500 words.
""" + RULES + FORMAT_WEEKLY


# ---------- ദിവസേന ----------

def latest_previous(date_str):
    files = sorted(p for p in HISTORY.glob("*.json") if p.stem < date_str)
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def collect(scans_cfg, sample):
    if sample:
        return json.loads((ROOT / "data" / "sample.json").read_text(encoding="utf-8"))["scans"]
    session = chartink.new_session()
    results = []
    for cfg in scans_cfg:
        entry = {"name": cfg["name"], "slug": cfg["slug"], "about": cfg.get("about", ""),
                 "stocks": [], "error": None}
        if cfg.get("max_show"):
            entry["max_show"] = cfg["max_show"]
        try:
            entry["stocks"] = chartink.run_scan(session, cfg)
        except Exception as e:  # noqa: BLE001
            entry["error"] = str(e)[:300]
        print(f"  {cfg['name']}: {len(entry['stocks'])} stocks" + (f"  (പിശക്: {entry['error']})" if entry["error"] else ""))
        results.append(entry)
    return results


def mark_new(scans, previous):
    prev = {s["slug"]: {x["symbol"] for x in s["stocks"]} for s in (previous or {}).get("scans", [])}
    for s in scans:
        before = prev.get(s["slug"])
        s["prev_count"] = len(before) if before is not None else None
        s["new"] = [] if before is None else sorted(x["symbol"] for x in s["stocks"] if x["symbol"] not in before)


def daily_prompt(date_str, scans, sector_rows, results=None, results_known=True, breadth_text=""):
    lines = [f"Date: {date_str}"]
    lines.append("\n## " + (breadth_text or "Market condition: not available today"))
    counts = {}
    for s in scans:
        for x in s["stocks"]:
            counts[x["symbol"]] = counts.get(x["symbol"], 0) + 1
        lines.append(f"\n## Scanner: {s['name']} — {s.get('about', '')}")
        if s["error"]:
            lines.append(f"ERROR fetching this scanner: {s['error']}")
            continue
        prev = s["prev_count"] if s["prev_count"] is not None else "unknown (first run)"
        lines.append(f"Count today: {len(s['stocks'])}; yesterday: {prev}")
        new = s["new"]
        lines.append(f"New today ({len(new)}): " + (", ".join(new[:30]) + (f" … +{len(new) - 30} more" if len(new) > 30 else "") if new else "none"))
        for x in sorted(s["stocks"], key=lambda x: -(x["change"] or 0))[:40]:
            res = f" | RESULTS {x['results']}" if x.get("results") and not s.get("max_show") else ""
            lines.append(f"- {x['symbol']} | {x.get('sector')} | close {x['close']} | change {x['change']}% | vol {x['volume']}{res}")
    multi = sorted(k for k, v in counts.items() if v > 1)
    lines.append("\nIn more than one scanner: " + (", ".join(multi) if multi else "none"))
    lines.append("\n## Sector summary (unique stocks across all scanners)")
    for r in sector_rows:
        lines.append(f"- {r['sector']}: {r['count']} stocks ({r['new']} new) — {', '.join(r['stocks'][:10])}")
    if results_known:
        lines.append("\n## Results coming (next 7 days): " + (", ".join(f"{k} on {v}" for k, v in (results or {}).items()) or "none"))
    else:
        lines.append("\nResults dates: unknown (calendar not available today)")
    stocks, secs = notable(scans, sector_rows, multi)
    lines.append("\nExplain these stocks: " + (", ".join(stocks) or "none"))
    lines.append("Explain these sectors: " + (", ".join(secs) or "none"))
    return "\n".join(lines)


def notable(scans, sector_rows, multi, max_stocks=10):
    """ശ്രദ്ധിക്കേണ്ട സ്റ്റോക്കുകൾ, മുൻഗണനാ ക്രമത്തിൽ:
    1) സിഗ്നൽ സ്കാനറുകളിൽ (HOLYGRAIL, MULTIBAGGER…) ഇന്ന് പുതിയവ  2) സിഗ്നൽ സ്കാനറുകളിലെ ബാക്കി
    3) വലിയ ലിസ്റ്റുകളിൽ (max_show ഉള്ളവ) പുതിയവ  4) ഒന്നിലധികം സ്കാനറിൽ  5) ഏറ്റവും കൂടുതൽ നീങ്ങിയവ"""
    signal = [s for s in scans if not s.get("max_show")]
    broad = [s for s in scans if s.get("max_show")]
    picked = []
    for s in signal:
        picked += s.get("new", [])
    for s in signal:
        picked += [x["symbol"] for x in sorted(s["stocks"], key=lambda x: -(x["change"] or 0))]
    for s in broad:
        picked += s.get("new", [])[:4]
    picked += list(multi)
    movers = sorted((x for s in scans for x in s["stocks"]), key=lambda x: -abs(x["change"] or 0))
    picked += [x["symbol"] for x in movers[:3]]
    seen, out = set(), []
    for sym in picked:
        if sym not in seen:
            seen.add(sym)
            out.append(sym)
    secs = [r["sector"] for r in sector_rows if r["sector"] != sectors.UNKNOWN][:3]
    return out[:max_stocks], secs


def sector_line(rows, top=5):
    known = [r for r in rows if r["sector"] != sectors.UNKNOWN][:top]
    return " · ".join(f"{r['sector']} {r['count']}" for r in known)


def daily_fallback(scans):
    return ""  # AI ഇല്ലെങ്കിൽ ചുരുക്കം ഒഴിവാക്കും; ബാക്കി റിപ്പോർട്ട് കോഡ് തന്നെ ഉണ്ടാക്കുന്നു


# ---------- ആഴ്ച ----------

def weekly_prompt(agg, perf_text="", breadth_text=""):
    d = agg["dates"]
    lines = [f"Week: {d[0]} to {d[-1]} ({len(d)} trading days)"]
    lines.append("\n## " + (breadth_text or "Market condition: not available"))
    for s in agg["scans"]:
        lines.append(f"\n## Scanner: {s['name']}")
        lines.append("Daily counts: " + ", ".join(f"{day}={c if c is not None else 'error'}" for day, c in s["daily"]))
        lines.append(f"Unique stocks this week: {s['unique']}")
        lines.append("In scanner every day: " + (", ".join(s["all_week"]) or "none"))
        lines.append("Entered during week: " + (", ".join(s["entered"]) or "none"))
        lines.append("Exited during week: " + (", ".join(s["exited"]) or "none"))
        for m in s["movers"]:
            lines.append(f"- {m['symbol']} | {m['sector']} | {m['days']}/{len(d)} days | week change {m['week_change']}%")
    lines.append("\n## Sectors (stock-days over the week; first day → last day unique stocks)")
    for r in agg["sectors"]:
        lines.append(f"- {r['sector']}: {r['stock_days']} stock-days; {r['first']} → {r['last']}")
    lines.append("\n## Scanner performance (all tracked new entries so far; close-to-close, no costs)")
    lines.append(perf_text or "No tracked entries yet.")
    return "\n".join(lines)


def weekly_fallback(agg):
    out = ["AI ഇന്ന് ലഭ്യമായില്ല — ആഴ്ചയിലെ റോ ഡാറ്റ:"]
    for s in agg["scans"]:
        out.append(f"- {s['name']}: {s['unique']} സ്റ്റോക്ക്; ആഴ്ച മുഴുവൻ: {', '.join(s['all_week']) or 'ഇല്ല'}")
    return "\n".join(out)


# ---------- പൊതുവായത് ----------

URL_RE = re.compile(r"\s*\(?\[?(?:https?://|www\.)\S+\]?\)?")
CITE_RE = re.compile(r"\s*\[\d+(?:,\s*\d+)*\]")


def clean(text):
    """ലിങ്കുകളും [1] പോലുള്ള സൈറ്റേഷൻ അടയാളങ്ങളും നീക്കും — കാരണം മാത്രം മതി."""
    return CITE_RE.sub("", URL_RE.sub("", text)).strip()


def ask_ai(system, drivers, prompt, fallback, no_ai):
    """ആദ്യം വാർത്ത തിരയലോടെ; പരാജയപ്പെട്ടാൽ തിരയലില്ലാതെ; അതും പോയാൽ റോ ഡാറ്റ."""
    if no_ai:
        return fallback, "AI ഇല്ല"
    if (os.environ.get("NEWS_SEARCH") or "on").strip().lower() != "off":
        try:
            text, label = ai.generate(system + drivers, prompt, search=True)
            return clean(text), label
        except Exception as e:  # noqa: BLE001
            print(f"  വാർത്ത തിരയൽ പരാജയം: {e}")
    try:
        text, label = ai.generate(system + NO_DRIVERS, prompt)
        return clean(text), label + " · കാരണങ്ങൾ ഇന്ന് ലഭ്യമായില്ല"
    except Exception as e:  # noqa: BLE001
        print(f"  {e}")
        return fallback, "AI ലഭ്യമായില്ല"


def site_base():
    base = os.environ.get("SITE_URL", "").strip().rstrip("/")
    if not base:
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if "/" in repo:
            owner, name = repo.split("/", 1)
            base = f"https://{owner.lower()}.github.io/{name}"
    return base


def make_pdf(html_path, name):
    """SEND_PDF=off ആണെങ്കിൽ PDF ഇല്ല. PDF റിപ്പോർട്ടുകൾ repo-യിൽ സേവ് ചെയ്യില്ല (out/ ഫോൾഡർ)."""
    if (os.environ.get("SEND_PDF") or "on").strip().lower() == "off":
        return None
    return pdf.render(html_path, ROOT / "out" / name)


def make_chart(bdata, name):
    if not bdata or (os.environ.get("SEND_CHART") or "on").strip().lower() == "off":
        return None
    return pdf.render_chart(bdata, ROOT / "out" / name)


def deliver(message, no_send, pdf_path=None, photo=None):
    if no_send:
        print("  (--no-send) മെസേജ്:\n" + message + (f"\n  PDF: {pdf_path}" if pdf_path else "") + (f"\n  ഗ്രാഫ്: {photo}" if photo else ""))
        return 0
    failed = False
    for label, fn in (("Telegram", notify.send_telegram), ("Discord", notify.send_discord)):
        try:
            print(f"  {label}: {fn(message, pdf_path, photo)}")
        except Exception as e:  # noqa: BLE001
            failed = True
            print(f"  {label}: പരാജയം — {e}")
    return 1 if failed else 0


def run_daily(args, lang, today):
    date_str = today.strftime("%Y-%m-%d")
    cfg = json.loads((ROOT / "scans.json").read_text(encoding="utf-8"))["scans"]

    print(f"[1/5] സ്കാനറുകൾ ഓടിക്കുന്നു ({date_str})")
    scans = collect(cfg, args.sample)

    print("[2/5] സെക്ടർ + ഇന്നലെയുമായി താരതമ്യം")
    mapping = sectors.load(allow_download=not args.sample)
    print(f"  സെക്ടർ പട്ടിക: {len(mapping)} സ്റ്റോക്ക്")
    sectors.tag(scans, mapping)
    if args.sample:
        previous = json.loads((ROOT / "data" / "sample.json").read_text(encoding="utf-8")).get("previous")
    else:
        previous = latest_previous(date_str)
    mark_new(scans, previous)
    sector_rows = sectors.summary(scans)

    results_map, ev_source = events.load(today.date(), allow_download=not args.sample)
    if args.sample:
        results_map = json.loads((ROOT / "data" / "sample.json").read_text(encoding="utf-8")).get("results", {})
        ev_source = "sample"
    results = events.tag(scans, results_map, today.date())
    # മുൻഗണന: സിഗ്നൽ സ്കാനറുകളിലും (max_show ഇല്ലാത്തവ) ഇന്ന് പുതിയവയിലും ഉള്ളവ
    key = {x["symbol"] for s in scans if not s.get("max_show") for x in s["stocks"]}
    key |= {sym for s in scans for sym in s.get("new", [])}
    results_key = {k: v for k, v in results.items() if k in key}
    print(f"  റിസൾട്ട് കലണ്ടർ: {ev_source}; അടുത്ത 7 ദിവസം: {', '.join(results) or 'ഇല്ല'}")

    bdata, bfresh, sig = None, False, None
    if args.sample:
        bdata, bfresh = json.loads((ROOT / "data" / "sample_breadth.json").read_text(encoding="utf-8")), True
    else:
        bdata, bfresh = breadth.load_fresh(today.date())
    if bdata:
        sig = breadth.signal(bdata)
        print(f"  മാർക്കറ്റ് അവസ്ഥ: {sig['emoji']} {sig['label']} ({bdata['asOf']}{'' if bfresh else ', പഴയത്'})")

    perf_rows = []
    if not args.sample:
        HISTORY.mkdir(parents=True, exist_ok=True)
        (HISTORY / f"{date_str}.json").write_text(
            json.dumps({"date": date_str, "scans": scans, "breadth": sig}, ensure_ascii=False, indent=1), encoding="utf-8")
        state = tracker.load()
        try:
            src, n = tracker.update_prices(state, today.date())
            print(f"  ട്രാക്കർ: {n} ദിവസത്തെ വില ചേർത്തു ({src})")
        except Exception as e:  # noqa: BLE001
            print(f"  ട്രാക്കർ വില പുതുക്കൽ പരാജയം: {e}")
        added = tracker.add_entries(state, date_str, scans, regime=sig["level"] if (sig and bfresh) else None)
        tracker.save(state)
        perf_rows = tracker.stats(state)
        print(f"  ട്രാക്കർ: {added} പുതിയ എൻട്രി, ആകെ {len(state['entries'])}")

    print("[3/5] AI വിശകലനം")
    raw, ai_label = ask_ai(SYSTEM_DAILY.format(lang=lang), DRIVERS_DAILY.format(lang=lang),
                           daily_prompt(date_str, scans, sector_rows, dict(list(results_key.items())[:15]),
                                        ev_source != "none",
                                        breadth.prompt_text(bdata, bfresh) if bdata else ""),
                           daily_fallback(scans), args.no_ai)
    ai_out = report.parse_ai(raw)
    print(f"  ഉപയോഗിച്ചത്: {ai_label}; കാരണങ്ങൾ: {len(ai_out['reasons'])}")
    counts = {}
    for s in scans:
        for x in s["stocks"]:
            counts[x["symbol"]] = counts.get(x["symbol"], 0) + 1
    note_syms, _ = notable(scans, sector_rows, sorted(k for k, v in counts.items() if v > 1))
    rows = report.notable_rows(scans, note_syms, ai_out, results)
    bmoves = breadth.sector_moves(bdata) if bdata else None

    print("[4/5] വെബ്‌പേജ്")
    site.build(ROOT / "docs", date_str, None, scans, sector_rows, ai_label,
               breadth_info=(bdata, bfresh) if bdata else None,
               rep={"summary": ai_out["summary"], "rows": rows, "sectors": ai_out["sectors"]})
    if perf_rows:
        site.build_performance(ROOT / "docs", date_str, perf_rows)

    print("[5/5] അയക്കുന്നു")
    base = site_base()
    msg = report.telegram_daily(date_str, sig, bfresh, scans, rows, sector_rows, bmoves, results_key, len(results),
                                ai_out, ai_label, f"{base}/reports/{date_str}.html" if base else "")
    pdf_path = make_pdf(ROOT / "docs" / "reports" / f"{date_str}.html", f"Market-Report-{date_str}.pdf")
    return deliver(msg, args.no_send, pdf_path, make_chart(bdata, f"Breadth-{date_str}.png"))


def run_weekly(args, lang, today):
    print("[1/4] ആഴ്ചയിലെ ഹിസ്റ്ററി വായിക്കുന്നു")
    week = weekly.load_week(HISTORY, today.date())
    if not week:
        print("  ഈ ആഴ്ചയിലെ ഹിസ്റ്ററി ഇല്ല — ഒന്നും ചെയ്യാനില്ല.")
        return 0
    agg = weekly.aggregate(week)
    end = agg["dates"][-1]
    print(f"  {agg['dates'][0]} – {end} ({len(agg['dates'])} ദിവസം)")

    print("[2/4] AI വിശകലനം")
    perf_rows = tracker.stats(tracker.load())
    bdata = None
    try:
        bdata = breadth.fetch()
    except Exception as e:  # noqa: BLE001
        print(f"  GM World ലഭ്യമായില്ല: {e}")
    btext = breadth.prompt_text(bdata, True, sessions=max(5, len(agg["dates"]))) if bdata else ""
    text, ai_label = ask_ai(SYSTEM_WEEKLY.format(lang=lang), DRIVERS_WEEKLY,
                            weekly_prompt(agg, tracker.stats_text(perf_rows), btext), weekly_fallback(agg), args.no_ai)
    print(f"  ഉപയോഗിച്ചത്: {ai_label}")

    print("[3/4] വെബ്‌പേജ്")
    site.build_weekly(ROOT / "docs", end, text, agg, ai_label, perf_rows,
                      breadth_info=(bdata, True) if bdata else None)

    print("[4/4] അയക്കുന്നു")
    msg = f"🗓️ <b>ആഴ്ച റാപ്പപ്പ്</b> · {report.short_date(agg['dates'][0])} – {report.short_date(end)}\n{report.RULE}\n"
    if bdata:
        msg += report.e(breadth.message_line(breadth.signal(bdata))) + "\n\n"
    msg += report.md_to_telegram(text)
    base = site_base()
    if base:
        msg += f'\n\n🔗 <a href="{base}/weekly/{end}.html">വിശദമായി</a> · 📄 PDF താഴെ'
    msg += f"\n<i>{report.e(ai_label)} · ഇത് സാമ്പത്തിക ഉപദേശമല്ല</i>"
    pdf_path = make_pdf(ROOT / "docs" / "weekly" / f"{end}.html", f"Weekly-Wrap-{end}.pdf")
    return deliver(msg, args.no_send, pdf_path, make_chart(bdata, f"Breadth-{end}.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weekly", action="store_true", help="ആഴ്ച റാപ്പപ്പ് ഉണ്ടാക്കും")
    ap.add_argument("--sample", action="store_true", help="Chartink-ന് പകരം data/sample.json ഉപയോഗിക്കും")
    ap.add_argument("--no-send", action="store_true", help="Telegram/Discord-ലേക്ക് അയക്കില്ല")
    ap.add_argument("--no-ai", action="store_true", help="AI വിളിക്കില്ല")
    args = ap.parse_args()

    lang = (os.environ.get("REPORT_LANGUAGE") or "").strip() or "Malayalam"
    today = datetime.now(IST)
    return run_weekly(args, lang, today) if args.weekly else run_daily(args, lang, today)


if __name__ == "__main__":
    sys.exit(main())
