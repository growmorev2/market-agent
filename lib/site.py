"""GitHub Pages-നുള്ള വെബ്‌പേജുകൾ ഉണ്ടാക്കുന്ന ഭാഗം.

docs/reports/YYYY-MM-DD.html  → ഓരോ ദിവസത്തെ റിപ്പോർട്ട്
docs/weekly/YYYY-MM-DD.html   → ആഴ്ച റാപ്പപ്പ് (ആഴ്ചയിലെ അവസാന തീയതി)
docs/performance.html         → സ്കാനർ പെർഫോമൻസ് (ദിവസവും പുതുക്കും)
docs/index.html               → എല്ലാ റിപ്പോർട്ടുകളുടെയും ലിസ്റ്റ് (പുതിയത് മുകളിൽ)
"""
import html
import re
from pathlib import Path

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--text:#1d2330;--muted:#667085;--line:#e4e7ec;--accent:#0f766e;--up:#15803d;--down:#b91c1c;--new:#b45309;--bar:#99d5cc}
@media (prefers-color-scheme:dark){:root{--bg:#0f1218;--card:#171b23;--text:#e6e8ec;--muted:#98a2b3;--line:#2a303b;--accent:#2dd4bf;--up:#4ade80;--down:#f87171;--new:#fbbf24;--bar:#1f5f57}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.65 "Noto Sans Malayalam","Noto Sans",system-ui,sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.5rem;margin:0 0 4px}h2{font-size:1.15rem;margin:28px 0 10px}h3{font-size:1rem;margin:18px 0 6px}
.muted{color:var(--muted);font-size:.9rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:14px 0}
.card h2{margin-top:0}
.table-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.92rem}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--muted);font-weight:600}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
td.wrap{white-space:normal}
td:first-child .badge{margin-top:2px}
td:first-child{white-space:normal;min-width:90px}
.up{color:var(--up)}.down{color:var(--down)}
.compact th,.compact td{padding:7px 4px;font-size:.85rem}
.sig{font-size:1.15rem;font-weight:700;margin:0 0 4px}
.chip{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:1px 10px;margin:3px 4px 3px 0;font-size:.85rem}
.badge.warn{color:var(--down);border-color:var(--down)}
.badge{display:inline-block;font-size:.72rem;font-weight:700;color:var(--new);border:1px solid var(--new);border-radius:6px;padding:0 5px;margin-left:6px}
.bar{position:relative}
.bar span{position:absolute;left:0;top:6px;bottom:6px;background:var(--bar);border-radius:4px;z-index:0}
.bar b{position:relative;z-index:1;font-weight:600}
a{color:var(--accent)}
ul.reports{list-style:none;padding:0}ul.reports li{padding:10px 0;border-bottom:1px solid var(--line)}
.err{color:var(--down)}
@media (max-width:560px){.col-wide{display:none}}
"""


def _page(title, body):
    return f"""<!doctype html>
<html lang="ml"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Malayalam:wght@400;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body><main>{body}</main></body></html>
"""


def _e(v):
    return html.escape(str(v))


def _inline(text):
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(text))


def md_to_html(md):
    """AI തരുന്ന ലളിതമായ Markdown (തലക്കെട്ട്, ലിസ്റ്റ്, bold) HTML ആക്കും."""
    out, in_list = [], False
    for raw in md.splitlines():
        line = raw.rstrip()
        bullet = re.match(r"^\s*[-*•]\s+(.*)", line)
        if bullet:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(bullet.group(1))}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        head = re.match(r"^(#{1,4})\s+(.*)", line)
        if head:
            out.append(f"<h3>{_inline(head.group(2))}</h3>")
        elif line.strip():
            out.append(f"<p>{_inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _fmt(v, digits=2):
    return "—" if v is None else f"{v:,.{digits}f}"


def _chg(v):
    cls = "up" if (v or 0) > 0 else "down" if (v or 0) < 0 else ""
    return f'<td class="num {cls}">{_fmt(v)}%</td>'


def _table(head, rows):
    return ('<div class="table-wrap"><table><thead><tr>' + head + "</tr></thead><tbody>"
            + "".join(rows) + "</tbody></table></div>")


def _bar_cell(value, maximum, label=None):
    w = 0 if not maximum else round(value / maximum * 100)
    return f'<td class="bar"><span style="width:{w}%"></span><b>{_e(label if label is not None else value)}</b></td>'


def _scan_table(scan):
    if scan.get("error"):
        return f'<p class="err">പിശക്: {_e(scan["error"])}</p>'
    if not scan["stocks"]:
        return '<p class="muted">ഇന്ന് ഈ സ്കാനറിൽ സ്റ്റോക്കുകൾ ഇല്ല.</p>'
    new = set(scan.get("new", []))
    rows = []
    ordered = sorted(scan["stocks"], key=lambda x: (x["symbol"] not in new, -(x["change"] or 0)))
    limit = scan.get("max_show") or len(ordered)
    for s in ordered[:limit]:
        badge = '<span class="badge">NEW</span>' if s["symbol"] in new else ""
        if s.get("results"):
            badge += f'<span class="badge warn">RESULT {_short(s["results"])}</span>'
        rows.append(
            f'<tr><td title="{_e(s.get("name") or "")}"><strong>{_e(s["symbol"])}</strong>{badge}</td>'
            f'<td class="col-wide">{_e(s.get("sector", ""))}</td>'
            f'<td class="num">{_fmt(s["close"])}</td>{_chg(s["change"])}</tr>'
        )
    more = ""
    if len(ordered) > limit:
        more = f'<p class="muted">+ {len(ordered) - limit} സ്റ്റോക്കുകൾ കൂടി (പുതിയവയും ഏറ്റവും കൂടുതൽ ഉയർന്നവയും മാത്രം കാണിക്കുന്നു)</p>'
    return _table('<th>Symbol</th><th class="col-wide">Sector</th><th class="num">Close</th><th class="num">Change</th>', rows) + more


def _sector_card(rows):
    if not rows:
        return ""
    mx = max(r["count"] for r in rows)
    body = [
        f'<tr><td class="wrap">{_e(r["sector"])}</td>{_bar_cell(r["count"], mx)}'
        f'<td class="num">{r["new"] or ""}</td>'
        f'<td class="col-wide wrap muted">{_e(", ".join(r["stocks"][:8]))}{" …" if len(r["stocks"]) > 8 else ""}</td></tr>'
        for r in rows
    ]
    return ('<div class="card"><h2>സെക്ടർ തിരിച്ച്</h2>'
            + _table('<th>Sector</th><th style="min-width:64px">Stocks</th><th class="num">New</th><th class="col-wide">Symbols</th>', body)
            + "</div>")


def _breadth_card(info, sessions=5):
    if not info:
        return ""
    from lib import breadth as B
    data, fresh = info
    sig = B.signal(data)
    rows = []
    for d, v in B.table(data, sessions):
        rows.append(f"<tr><td>{_e(d)}</td>" + "".join(f'<td class="num">{v[k]:.0f}</td>' for k in ("t20", "t50", "t200", "hom"))
                    + _chg(v["nh"]) + "</tr>")
    ab = {"e20": "20 EMA", "d50": "50 DMA", "d200": "200 DMA"}
    chips = "".join(f'<span class="chip">{n}-ന് മുകളിൽ {sig["above"][k]}%</span>' for k, n in ab.items() if sig["above"].get(k) is not None)
    mv = B.sector_moves(data)
    fmt = lambda rs: _e(", ".join(f"{r['sector']} {r['now']} ({r['change']:+d})" for r in rs)) or '<span class="muted">ഇല്ല</span>'
    notes = "".join(f'<p class="muted">• {_e(n)}</p>' for n in sig["notes"])
    stale = "" if fresh else f'<p class="err">ഇന്നത്തെ GM World ഡാറ്റ വന്നില്ല — {_e(data["asOf"])}-ലേതാണ് കാണിക്കുന്നത്.</p>'
    return (f'<div class="card"><h2>മാർക്കറ്റ് അവസ്ഥ</h2>{stale}'
            f'<p class="sig">{sig["emoji"]} {_e(sig["label"])} <span class="muted">· {_e(sig["trend"])}</span></p>{notes}'
            f'<p class="muted">GM World · {_e(data["asOf"])}</p>{chips}'
            + '<div class="compact">' + _table('<th>Date</th><th class="num">20</th><th class="num">50</th><th class="num">200</th><th class="num">Hom</th><th class="num">NH-NL</th>', rows) + "</div>"
            + "<h3>സെക്ടർ മൊമെന്റം (Landry, 5 സെഷനിലെ മാറ്റം)</h3>"
            + f"<p><strong>മുന്നിൽ:</strong> {fmt(mv['leaders'])}</p>"
            + f"<p><strong>ഉയരുന്നു:</strong> {fmt(mv['gainers'])}</p>"
            + f"<p><strong>താഴുന്നു:</strong> {fmt(mv['losers'])}</p></div>")


def _short(ds):
    from datetime import datetime
    return datetime.strptime(ds, "%Y-%m-%d").strftime("%d %b")


def _perf_card(rows, title="സ്കാനർ പെർഫോമൻസ്"):
    if not rows:
        return ""
    body = []
    for r in rows:
        trs = []
        for n, h in r["h"].items():
            if not h:
                trs.append(f'<tr><td>{n} ദിവസം</td><td class="muted" colspan="4">ഡാറ്റ ആയിട്ടില്ല</td></tr>')
            else:
                trs.append(f'<tr><td>{n} ദിവസം</td><td class="num">{h["n"]}</td><td class="num">{h["win"]}%</td>'
                           f'{_chg(h["avg"])}{_chg(h["median"])}</tr>')
        extra = ""
        if r.get("regime"):
            em = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
            extra += "<p><strong>10 ദിവസം, മാർക്കറ്റ് അവസ്ഥ അനുസരിച്ച്:</strong> " + " · ".join(
                f'{em[k]} n={v["n"]}, win {v["win"]}%, avg {v["avg"]:+}%' for k, v in r["regime"].items()) + "</p>"
        if r["best"]:
            extra += "<p><strong>മികച്ചത് (20d):</strong> " + _e(", ".join(f"{a} {c:+}%" for a, _, c in r["best"])) + "</p>"
        if r["worst"]:
            extra += "<p><strong>മോശം (20d):</strong> " + _e(", ".join(f"{a} {c:+}%" for a, _, c in r["worst"])) + "</p>"
        body.append(f'<h3>{_e(r["name"])} <span class="muted">({r["total"]} എൻട്രി, {r["open"]} ട്രാക്ക് ചെയ്യുന്നു)</span></h3>'
                    + _table('<th>ശേഷം</th><th class="num">n</th><th class="num">Win</th><th class="num">Avg</th><th class="num">Median</th>', trs)
                    + extra)
    return (f'<div class="card"><h2>{title}</h2>'
            '<p class="muted">സ്കാനറിൽ പുതുതായി വന്ന ദിവസത്തെ ക്ലോസിൽ നിന്ന് N ട്രേഡിംഗ് ദിവസം കഴിഞ്ഞുള്ള ക്ലോസ് വരെ. '
            'ചെലവ്, സ്റ്റോപ്പ് ലോസ് ഇല്ലാത്ത കണക്ക്. n = എത്ര സാമ്പിൾ; 20-ൽ താഴെ ആണെങ്കിൽ നിഗമനത്തിന് നേരത്തെയാണ്.</p>'
            + "".join(body) + "</div>")


def build_performance(out_dir, date_str, rows):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    body = ('<p><a href="index.html">← എല്ലാ റിപ്പോർട്ടുകളും</a></p>'
            f'<h1>സ്കാനർ പെർഫോമൻസ്</h1><p class="muted">പുതുക്കിയത്: {_e(date_str)} · ഇത് സാമ്പത്തിക ഉപദേശമല്ല</p>'
            + _perf_card(rows, "5 / 10 / 20 ദിവസത്തിന് ശേഷം"))
    (out / "performance.html").write_text(_page("Scanner Performance", body), encoding="utf-8")
    _write_index(out)


def _write_index(out):
    daily = sorted((p.stem for p in (out / "reports").glob("*.html")), reverse=True)
    weekly = sorted((p.stem for p in (out / "weekly").glob("*.html")), reverse=True) if (out / "weekly").exists() else []
    w_items = "".join(f'<li><a href="weekly/{d}.html">ആഴ്ച അവസാനിച്ചത് {d}</a></li>' for d in weekly[:12])
    d_items = "".join(f'<li><a href="reports/{d}.html">{d}</a></li>' for d in daily)
    body = (
        "<h1>മാർക്കറ്റ് ഏജന്റ്</h1>"
        '<p class="muted">AI റിപ്പോർട്ടുകൾ · ഇത് സാമ്പത്തിക ഉപദേശമല്ല</p>'
        + ('<p><a href="performance.html">📈 സ്കാനർ പെർഫോമൻസ്</a></p>' if (out / "performance.html").exists() else "")
        + (f'<h2>ആഴ്ച റാപ്പപ്പ്</h2><ul class="reports">{w_items}</ul>' if w_items else "")
        + f'<h2>ദിവസേനയുള്ള റിപ്പോർട്ട്</h2><ul class="reports">{d_items}</ul>'
    )
    (out / "index.html").write_text(_page("Market Agent", body), encoding="utf-8")


def build(out_dir, date_str, report_md, scans, sector_rows, ai_label, breadth_info=None):
    out = Path(out_dir)
    (out / "reports").mkdir(parents=True, exist_ok=True)
    sections = "".join(
        f'<div class="card"><h2>{_e(s["name"])} '
        f'<span class="muted">({len(s["stocks"])} സ്റ്റോക്ക്, {len(s.get("new", []))} പുതിയത്)</span></h2>'
        f"{_scan_table(s)}</div>"
        for s in scans
    )
    body = (
        '<p><a href="../index.html">← എല്ലാ റിപ്പോർട്ടുകളും</a></p>'
        f"<h1>മാർക്കറ്റ് റിപ്പോർട്ട് — {_e(date_str)}</h1>"
        f'<p class="muted">വിശകലനം: {_e(ai_label)} · ഇത് സാമ്പത്തിക ഉപദേശമല്ല</p>'
        f'<div class="card">{md_to_html(report_md)}</div>'
        f"{_breadth_card(breadth_info)}"
        f"{_sector_card(sector_rows)}"
        f"<h2>സ്കാനർ റിസൾട്ടുകൾ</h2>{sections}"
    )
    (out / "reports" / f"{date_str}.html").write_text(_page(f"Report {date_str}", body), encoding="utf-8")
    _write_index(out)


def build_weekly(out_dir, end_date, report_md, agg, ai_label, perf_rows=None, breadth_info=None):
    out = Path(out_dir)
    (out / "weekly").mkdir(parents=True, exist_ok=True)
    days = agg["dates"]
    parts = []

    if agg["sectors"]:
        mx = max(r["stock_days"] for r in agg["sectors"])
        rows = []
        for r in agg["sectors"]:
            diff = r["last"] - r["first"]
            cls = "up" if diff > 0 else "down" if diff < 0 else "muted"
            rows.append(f'<tr><td class="wrap">{_e(r["sector"])}</td>{_bar_cell(r["stock_days"], mx)}'
                        f'<td class="num">{r["first"]}→{r["last"]} <span class="{cls}">({diff:+d})</span></td></tr>')
        parts.append('<div class="card"><h2>സെക്ടർ — ആഴ്ച മുഴുവൻ</h2>'
                     '<p class="muted">Stock-days = ഓരോ ദിവസവും സ്കാനറിൽ വന്ന സ്റ്റോക്കുകളുടെ ആകെ. '
                     'വലത്: ആഴ്ചയുടെ ആദ്യ ദിവസം → അവസാന ദിവസം.</p>'
                     + _table('<th>Sector</th><th style="min-width:64px">Days</th><th class="num">Trend</th>', rows)
                     + "</div>")

    for s in agg["scans"]:
        counts = [c for _, c in s["daily"] if c is not None]
        mx = max(counts) if counts else 0
        daily_rows = [f'<tr><td>{_e(d)}</td>' + (_bar_cell(c, mx) if c is not None else '<td class="err">പിശക്</td>') + "</tr>"
                      for d, c in s["daily"]]
        mover_rows = [f'<tr><td><strong>{_e(m["symbol"])}</strong></td><td class="col-wide">{_e(m["sector"])}</td>'
                      f'<td class="num">{m["days"]}/{len(days)}</td>{_chg(m["week_change"])}</tr>'
                      for m in s["movers"]]

        def chips(label, items):
            return f'<p><strong>{label}:</strong> {_e(", ".join(items)) if items else "<span class=muted>ഇല്ല</span>"}</p>'

        parts.append(
            f'<div class="card"><h2>{_e(s["name"])} <span class="muted">({s["unique"]} വ്യത്യസ്ത സ്റ്റോക്ക്)</span></h2>'
            + _table('<th>Date</th><th style="min-width:120px">Stocks</th>', daily_rows)
            + chips("ആഴ്ച മുഴുവൻ ഉണ്ടായിരുന്നവ", s["all_week"])
            + chips("ആഴ്ചയിൽ പുതുതായി വന്നവ", s["entered"])
            + chips("ആഴ്ചയിൽ പുറത്തായവ", s["exited"])
            + (("<h3>2+ ദിവസം വന്നവ — ആഴ്ചയിലെ വില മാറ്റം</h3>"
                + _table('<th>Symbol</th><th class="col-wide">Sector</th><th class="num">Days</th><th class="num">Week</th>', mover_rows))
               if mover_rows else "")
            + "</div>"
        )

    period = f"{days[0]} – {days[-1]}" if days else end_date
    body = (
        '<p><a href="../index.html">← എല്ലാ റിപ്പോർട്ടുകളും</a></p>'
        f"<h1>ആഴ്ച റാപ്പപ്പ്</h1><p class=\"muted\">{_e(period)} · {len(days)} ട്രേഡിംഗ് ദിവസം · "
        f"വിശകലനം: {_e(ai_label)} · ഇത് സാമ്പത്തിക ഉപദേശമല്ല</p>"
        f'<div class="card">{md_to_html(report_md)}</div>' + _breadth_card(breadth_info, max(5, len(days)))
        + "".join(parts) + _perf_card(perf_rows or [])
    )
    (out / "weekly" / f"{end_date}.html").write_text(_page(f"Weekly {end_date}", body), encoding="utf-8")
    _write_index(out)
