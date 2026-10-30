"""GitHub Pages-നുള്ള വെബ്‌പേജുകൾ ഉണ്ടാക്കുന്ന ഭാഗം.

docs/reports/YYYY-MM-DD.html  → ഓരോ ദിവസത്തെ റിപ്പോർട്ട്
docs/weekly/YYYY-MM-DD.html   → ആഴ്ച റാപ്പപ്പ് (ആഴ്ചയിലെ അവസാന തീയതി)
docs/performance.html         → സ്കാനർ പെർഫോമൻസ് (ദിവസവും പുതുക്കും)
docs/index.html               → എല്ലാ റിപ്പോർട്ടുകളുടെയും ലിസ്റ്റ് (പുതിയത് മുകളിൽ)
"""
import html
import json
import re
from pathlib import Path

from lib.report import nice_date

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
.ranked td:first-child{min-width:0;width:2em}.ranked th,.ranked td{padding:7px 4px;font-size:.88rem}.ranked .badge{margin-left:3px;padding:0 3px;font-size:.65rem}
.up{color:var(--up)}.down{color:var(--down)}
.charts{display:grid;gap:10px;margin:12px 0}.charts svg{display:block;border:1px solid var(--line);border-radius:10px}
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
@media print{body{background:#fff}main{max-width:none;padding:0}.table-wrap{overflow:visible}tr{break-inside:avoid}h2,h3{break-after:avoid}.charts svg{break-inside:avoid}.card{margin:8px 0}.extra,.print-hide{display:none}.print-note{display:block!important}a[href^="../index"]{display:none}}
.print-note{display:none}
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
    if scan.get("ranked"):
        return _ranked_table(scan, new)
    rows = []
    ordered = sorted(scan["stocks"], key=lambda x: (x["symbol"] not in new, -(x["change"] or 0)))
    limit = scan.get("max_show") or len(ordered)
    for i, s in enumerate(ordered[:limit]):
        badge = '<span class="badge">NEW</span>' if s["symbol"] in new else ""
        if s.get("results"):
            badge += f'<span class="badge warn">RESULT {_short(s["results"])}</span>'
        rows.append(
            f'<tr{" class=extra" if i >= 20 else ""}><td title="{_e(s.get("name") or "")}"><strong>{_e(s["symbol"])}</strong>{badge}</td>'
            f'<td class="col-wide">{_e(s.get("sector", ""))}</td>'
            f'<td class="num">{_fmt(s["close"])}</td>{_chg(s["change"])}</tr>'
        )
    more = ""
    if len(ordered) > 20:
        more += f'<p class="muted print-note">PDF-ൽ ആദ്യ 20 മാത്രം · മുഴുവൻ ലിസ്റ്റ് വെബ്‌സൈറ്റിൽ ({len(ordered)} സ്റ്റോക്ക്)</p>'
    if len(ordered) > limit:
        more = f'<p class="muted">+ {len(ordered) - limit} സ്റ്റോക്കുകൾ കൂടി (പുതിയവയും ഏറ്റവും കൂടുതൽ ഉയർന്നവയും മാത്രം കാണിക്കുന്നു)</p>'
    return _table('<th>Symbol</th><th class="col-wide">Sector</th><th class="num">Close</th><th class="num">Change</th>', rows) + more


def _ranked_table(scan, new):
    rows = []
    for x in sorted(scan["stocks"], key=lambda x: x["rank"]):
        badge = '<span class="badge">NEW</span>' if x["symbol"] in new else ""
        up = x.get("rank_up")
        if up is None:
            mv = '<td class="num muted">—</td>'
        elif up > 0:
            mv = f'<td class="num up">↑{up}</td>'
        elif up < 0:
            mv = f'<td class="num down">↓{-up}</td>'
        else:
            mv = '<td class="num muted">=</td>'
        rows.append(f'<tr><td class="num">{x["rank"]}</td><td><strong>{_e(x["symbol"])}</strong>{badge}</td>'
                    f'<td class="col-wide">{_e(x.get("sector", ""))}</td>'
                    f'<td class="num"><strong>{_fmt(x.get("score"), 1)}</strong></td>{mv}'
                    f'<td class="num col-wide">{_fmt(x["close"])}</td>{_chg(x["change"])}</tr>')
    return '<div class="ranked">' + _table('<th class="num">#</th><th>Symbol</th><th class="col-wide">Sector</th><th class="num">Score</th>'
                  '<th class="num">റാങ്ക്</th><th class="num col-wide">Close</th><th class="num">%</th>', rows) + "</div>"


def _sector_card(rows):
    if not rows:
        return ""
    mx = max(r["count"] for r in rows)
    body = [
        f'<tr><td class="wrap">{_e(r["sector"])}</td>{_bar_cell(r["count"], mx)}'
        f'<td class="num">{r["new"] or ""}</td>'
        f'<td class="col-wide wrap muted print-hide">{_e(", ".join(r["stocks"][:8]))}{" …" if len(r["stocks"]) > 8 else ""}</td></tr>'
        for r in rows
    ]
    return ('<div class="card"><h2>സെക്ടർ തിരിച്ച്</h2>'
            + _table('<th>Sector</th><th style="min-width:64px">Stocks</th><th class="num">New</th><th class="col-wide print-hide">Symbols</th>', body)
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
    from lib import charts as C
    graphs = f'<div class="charts">{C.breadth_lines(data)}{C.nhnl_bars(data)}</div>'
    return (f'<div class="card"><h2>മാർക്കറ്റ് അവസ്ഥ</h2>{stale}'
            f'<p class="sig">{sig["emoji"]} {_e(sig["label"])} <span class="muted">· {_e(sig["trend"])}</span></p>{notes}'
            f'<p class="muted">GM World · {_e(data["asOf"])}</p>{chips}{graphs}'
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
        + ('<p><a href="strategy.html">📋 Stock selection strategy (Momentum / Value)</a></p>' if (out / "strategy.html").exists() else "")
        + ('<p><a href="performance.html">📈 സ്കാനർ പെർഫോമൻസ്</a></p>' if (out / "performance.html").exists() else "")
        + (f'<h2>ആഴ്ച റാപ്പപ്പ്</h2><ul class="reports">{w_items}</ul>' if w_items else "")
        + f'<h2>ദിവസേനയുള്ള റിപ്പോർട്ട്</h2><ul class="reports">{d_items}</ul>'
    )
    (out / "index.html").write_text(_page("Market Agent", body), encoding="utf-8")


def _summary_only(rep):
    if not rep or not rep.get("summary"):
        return ""
    return f'<div class="card"><h2>💡 ചുരുക്കം</h2><p>{_e(rep["summary"])}</p></div>'


def _summary_card(rep):
    if not rep:
        return ""
    out = ""
    rows = rep.get("rows") or []
    if rows:
        trs = []
        for r in rows:
            warn = f'<span class="badge warn">RESULT {_short(r["results"])}</span>' if r.get("results") else ""
            trs.append(f'<tr><td><strong>{_e(r["symbol"])}</strong>{warn}<div class="muted">{_e(" · ".join(r["scanners"]))}</div></td>'
                       f'<td class="col-wide">{_e(r["sector"])}</td><td class="num">{_fmt(r["close"])}</td>{_chg(r["change"])}'
                       f'<td class="wrap">{_e(r["reason"] or "—")}</td></tr>')
        out += ('<div class="card"><h2>⭐ ശ്രദ്ധിക്കേണ്ടവ</h2>'
                '<p class="muted">ഒന്നിലധികം സ്കാനറിൽ ഉള്ളവ, ഇന്ന് പുതുതായി വന്നവ, ഏറ്റവും കൂടുതൽ നീങ്ങിയവ — കാരണം വാർത്തയിൽ നിന്ന്</p>'
                + _table('<th>Stock</th><th class="col-wide">Sector</th><th class="num">Close</th><th class="num">%</th><th>കാരണം</th>', trs)
                + "</div>")
    if rep.get("sectors"):
        items = "".join(f"<li><strong>{_e(k)}</strong> – {_e(v)}</li>" for k, v in rep["sectors"].items())
        out += f'<div class="card"><h2>🏭 സെക്ടർ കാരണങ്ങൾ</h2><ul>{items}</ul></div>'
    return out


def build(out_dir, date_str, report_md, scans, sector_rows, ai_label, breadth_info=None, rep=None):
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
        f"<h1>മാർക്കറ്റ് റിപ്പോർട്ട്</h1><p class=\"muted\">{_e(nice_date(date_str))}</p>"
        f'<p class="muted">വിശകലനം: {_e(ai_label)} · ഇത് സാമ്പത്തിക ഉപദേശമല്ല</p>'
        + (f'<div class="card">{md_to_html(report_md)}</div>' if report_md else "")
        + _summary_only(rep)
        + _breadth_card(breadth_info)
        + _summary_card(rep)
        + f"{_sector_card(sector_rows)}"
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


# ---------- Strategy പേജ് (Momentum / Value portfolio) ----------

STRAT_CSS = """
.tabs{display:flex;gap:8px;margin:14px 0}
.tabs button{font:inherit;font-weight:600;padding:8px 16px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--text);cursor:pointer}
.tabs button[aria-selected=true]{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent)}
.flt{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:.88rem;margin:6px 0 2px}
.flt label{display:inline-flex;gap:5px;align-items:center;cursor:pointer}
.ok{color:var(--up)}.no{color:var(--down)}
.fl{display:inline-block;font-size:.72rem;border-radius:6px;padding:0 5px;margin:2px 3px 0 0;border:1px solid var(--line)}
.fl.no{border-color:var(--down)}
.gate{font-weight:600}
main{max-width:1100px}
.phead{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px}
.phead h2{margin:0}
.psort{font-size:.88rem;color:var(--muted)}.psort select{font:inherit;padding:4px 8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--text)}
.ptable th.sortable{cursor:pointer;user-select:none}.ptable th.sortable:hover{color:var(--accent)}
.ptable .prow{cursor:pointer}.ptable .prow:hover td,.ptable .prow.open td{background:color-mix(in srgb,var(--accent) 6%,transparent)}
.ptable .prow.open td{border-bottom-color:transparent}
.ptable .pdet td{white-space:normal;background:color-mix(in srgb,var(--accent) 4%,transparent);padding:4px 10px 12px}
.ptable .badge{margin-left:4px;padding:0 4px;font-size:.65rem}
.ph-only{display:none}
@media (max-width:560px){.ph-hide{display:none}.ph-only{display:inline}div.ph-only{display:block}.ptable th,.ptable td{padding:7px 4px;font-size:.8rem}.ptable td:first-child{min-width:0;max-width:120px}.ptable .badge{display:none}}
.cklist{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:2px 14px;font-size:.82rem}
.pgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px;margin-top:6px}
.pcard{border:1px solid var(--line);border-radius:12px;padding:12px 14px;background:var(--bg);min-width:0}
.pcard header{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.psym{font-weight:700;font-size:1.08rem}.psym .badge{vertical-align:2px}
.pnow{text-align:right}.pnow div{font-size:1.45rem;font-weight:700;line-height:1.1;font-variant-numeric:tabular-nums}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:8px;margin:10px 0}
.tiles>div{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 8px;display:flex;flex-direction:column;min-width:0}
.tiles small{color:var(--muted);font-size:.72rem}.tiles b{font-size:1rem;font-variant-numeric:tabular-nums}.tiles span{font-size:.74rem;line-height:1.3}
.days{display:flex;flex-wrap:wrap;gap:4px;margin:4px 0 8px}
.dchip{display:flex;flex-direction:column;border-radius:6px;padding:2px 7px;font-size:.82rem;font-weight:600;font-variant-numeric:tabular-nums}
.dchip small{font-weight:400;font-size:.66rem;color:var(--muted)}
.dchip.pos{background:color-mix(in srgb,var(--up) 12%,transparent);color:var(--up)}.dchip.neg{background:color-mix(in srgb,var(--down) 12%,transparent);color:var(--down)}
.checks{display:flex;flex-wrap:wrap;gap:4px}.ck{font-size:.72rem;border-radius:999px;padding:1px 8px;border:1px solid var(--line)}
.ck.ok{color:var(--up)}.ck.no{color:var(--down);border-color:color-mix(in srgb,var(--down) 40%,transparent)}
.pcard details{margin-top:6px;font-size:.8rem}.pcard summary{cursor:pointer}
@media (max-width:560px){.pgrid{grid-template-columns:minmax(0,1fr)}}
.strip{display:inline-flex;gap:1px;height:46px;align-items:center;vertical-align:middle;cursor:pointer}
.strip i{display:block;width:4px;border-radius:1px}
details summary{list-style:none}details summary::-webkit-details-marker{display:none}
details .chip{font-size:.75rem}
.tvbtns{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 8px}
.tvbtns button{font:inherit;font-size:.88rem;font-weight:600;padding:6px 12px;border-radius:8px;border:1px solid var(--accent);background:var(--card);color:var(--accent);cursor:pointer}
.kpi{display:flex;flex-wrap:wrap;gap:8px 22px;font-size:.9rem}.kpi b{font-size:1.15rem}
"""

STRAT_JS = r"""
const R = JSON.parse(document.getElementById('sdata').textContent);
let tab = 'momentum';
try { tab = localStorage.getItem('strat-tab') || 'momentum'; } catch (e) {}
const off = { momentum: new Set(), value: new Set() };
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const num = (v, d = 2) => v == null ? '—' : Number(v).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = v => v == null ? '—' : `<span class="${v >= 0 ? 'up' : 'down'}">${v >= 0 ? '+' : ''}${num(v, 1)}%</span>`;
const table = (head, rows) => rows.length ? `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${rows.join('')}</tbody></table></div>` : '<p class="muted">ഇല്ല</p>';
function status(r) {
  const f = r.filters.filter(x => !off[tab].has(x.k));
  if (f.some(x => x.hard && !x.ok)) return 'reject';
  const fails = f.filter(x => !x.ok).length;
  return fails === 0 ? 'buy' : fails <= 2 ? 'watch' : 'reject';
}
function flags(r, onlyFail) {
  return r.filters.filter(x => !off[tab].has(x.k) && (!onlyFail || !x.ok))
    .map(x => `<span class="fl ${x.ok ? 'ok' : 'no'}" title="${esc(x.note)}">${x.ok ? '✓' : '✗'} ${esc(x.label)}</span>`).join('');
}
function tvButtons(list, label) {
  if (!list.length) return '';
  return `<div class="tvbtns"><button type="button" id="tv-copy">📋 Copy to TradingView</button><button type="button" id="tv-file">⬇️ .txt (Import list)</button><span class="muted" id="tv-msg"></span></div>`;
}
function wireTv(syms, fname) {
  const tvList = syms.map(s => 'NSE:' + s).join(',');
  const msg = t => { const m = document.getElementById('tv-msg'); if (m) m.textContent = t; };
  const cp = document.getElementById('tv-copy');
  if (cp) cp.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(tvList); }
    catch (e) { const ta = document.createElement('textarea'); ta.value = tvList; document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); } catch (e2) {} ta.remove(); }
    msg(`✓ ${syms.length} symbol കോപ്പി ചെയ്തു — TradingView watchlist-ൽ "Add symbol" ബോക്സിൽ paste ചെയ്യുക`);
  });
  const fb = document.getElementById('tv-file');
  if (fb) fb.addEventListener('click', () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([tvList], { type: 'text/plain' }));
    a.download = fname; document.body.appendChild(a); a.click(); a.remove();
    msg('✓ ഫയൽ ഡൗൺലോഡ് ചെയ്തു — TradingView watchlist മെനു → Import list');
  });
}
function dmy(s) { const [y, m, d] = s.split('-'); return `${+d} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+m - 1]}`; }
function strip(e) {
  const pts = Object.entries(e.series).map(([d, c]) => [d, (c / e.base - 1) * 100]);
  if (!pts.length) return '';
  const max = Math.max(5, ...pts.map(p => Math.abs(p[1])));
  const bars = pts.map(([d, p]) => `<i title="${dmy(d)}: ${p >= 0 ? '+' : ''}${p.toFixed(1)}%" style="height:${Math.max(2, 22 * Math.abs(p) / max)}px;background:var(${p >= 0 ? '--up' : '--down'});${p >= 0 ? 'align-self:flex-end' : 'align-self:flex-start'}"></i>`).join('');
  return `<span class="strip">${bars}</span>`;
}
function renderPead() {
  const P = R.pead;
  if (!P) { document.getElementById('sbody').innerHTML = '<div class="card"><p class="muted">PEAD ഡാറ്റ ഇന്ന് ലഭ്യമായില്ല.</p></div>'; return; }
  const now = e => { const v = Object.values(e.series); return v.length ? (v[v.length - 1] / e.base - 1) * 100 : null; };
  const best = e => { const v = Object.values(e.series); return v.length ? (Math.max(...v) / e.base - 1) * 100 : null; };
  let sortBy = 'now', sortAsc = false;
  try { sortBy = localStorage.getItem('pead-sort') || 'now'; sortAsc = localStorage.getItem('pead-asc') === '1'; } catch (e) {}
  const keys = { now: e => now(e) ?? -999, max: e => best(e) ?? -999, sue: e => e.sue ?? -999, score: e => e.score * 1000 + (now(e) ?? 0),
                 date: e => e.res_date, growth: e => e.g_yoy ?? -999, react: e => e.react ?? -999, symbol: e => e.symbol };
  if (!keys[sortBy]) sortBy = 'now';
  const act = P.active.slice().sort((a, b) => { const x = keys[sortBy](a), y = keys[sortBy](b); const r = x < y ? 1 : x > y ? -1 : 0; return sortAsc ? -r : r; });
  const avg = act.length ? act.reduce((t, e) => t + (now(e) || 0), 0) / act.length : null;
  const up = act.filter(e => (now(e) || 0) > 0).length;
  const GT = { 'ശരിക്കും വലിയ വളർച്ച': ['🚀', 'up'], 'ശക്തം': ['💪', 'up'], 'മാന്യമായ വളർച്ച': ['👍', ''], 'ചെറിയ വളർച്ച': ['➖', 'muted'], 'വെറും തിരിച്ചുവരവ്': ['⚠️', 'down'] };
  let h = `<div class="card"><div class="kpi"><span>ട്രാക്കിൽ <b>${act.length}</b></span><span>ഇന്ന് പുതിയത് <b>${P.added.length}</b></span>
    <span>ശരാശരി <b>${pct(avg)}</b></span><span>ഉയർന്നവ <b>${up}/${act.length}</b></span></div>
    <p class="muted">Excellent റിസൾട്ട് (7-ൽ 5+; EPS ≥30%, Sales ≥15%, Quality നിർബന്ധം) · % = റിസൾട്ടിന് തൊട്ടുമുമ്പുള്ള close-ൽ നിന്ന് · 🔥 SUE 2+ വലിയ surprise · 🚀 ശക്തമായ പ്രതികരണം · 🚀/💪/👍/⚠️ വളർച്ചയുടെ നില · വരിയിൽ തൊട്ടാൽ മുഴുവൻ വിവരം.</p></div>`;
  const cols = [['symbol', 'Stock', ''], ['date', 'Result', 'ph-hide'], ['score', 'Score', 'num ph-hide'], ['growth', 'വളർച്ച', 'num'], ['sue', 'SUE', 'num'],
                ['react', 'പ്രതികരണം', 'num ph-hide'], ['now', 'ഇപ്പോൾ', 'num'], ['max', 'Max', 'num col-wide'], ['', 'ഓരോ ദിവസവും', 'col-wide']];
  const head = cols.map(([k, l, c]) => k ? `<th class="${c} sortable" data-k="${k}">${l}${sortBy === k ? (sortAsc ? ' ▲' : ' ▼') : ''}</th>` : `<th class="${c}">${l}</th>`).join('');
  const rows = act.map((e, i) => {
    const n = now(e), mx = best(e), gt = GT[e.growth_tag] || ['', 'muted'];
    const tag = e.growth_tag ? `<span title="${esc(e.growth_tag)}${e.base_effect ? ' (2 വർഷം മുമ്പുമായി)' : ''}">${gt[0]}</span> ` : '';
    const days = Object.entries(e.series).map(([d, c], j) => { const p = (c / e.base - 1) * 100;
      return `<span class="dchip ${p >= 0 ? 'pos' : 'neg'}"><small>D${j + 1} · ${dmy(d)}</small>${p >= 0 ? '+' : ''}${p.toFixed(1)}%</span>`; }).join('');
    const tiles = [
      ['Profit വളർച്ച (YoY)', e.g_yoy == null ? '—' : pct(e.g_yoy), e.growth_tag ? gt[0] + ' ' + esc(e.growth_tag) + (e.base_effect ? ' (2Y അടിസ്ഥാനം)' : '') : ''],
      e.base_effect ? ['2 വർഷം മുമ്പത്തേക്കാൾ', e.g2y == null ? '—' : pct(e.g2y), 'base effect — കഴിഞ്ഞ വർഷം ലാഭം കുറവായിരുന്നു'] : null,
      ['SUE', e.sue == null ? '—' : (e.sue >= 2 ? '🔥 ' : '') + e.sue.toFixed(1), e.sue == null ? 'ഹിസ്റ്ററി കുറവ്' : e.sue >= 2 ? 'വലിയ surprise' : e.sue >= 1 ? 'പോസിറ്റീവ്' : 'പ്രതീക്ഷിച്ചത്'],
      ['പ്രതികരണം', e.react == null ? '—' : (e.react_ok ? '🚀 ' : '') + pct(e.react), (e.volx != null ? e.volx.toFixed(1) + '× volume' : '') + (e.react_date ? ' · ' + dmy(e.react_date) : '')],
      e.margin != null ? ['Margin', `${e.margin}% ${e.margin >= e.margin_prev ? '↑' : '↓'}`, 'മുൻ വർഷം ' + e.margin_prev + '%'] : null,
    ].filter(Boolean).map(([l, v, sub]) => `<div><small>${l}</small><b>${v}</b><span class="muted">${sub}</span></div>`).join('');
    const checks = e.checks.map(c => `<div class="${c[1] ? 'up' : 'down'}">${c[1] ? '✓' : '✗'} <b>${esc(c[0])}</b> <span class="muted">${esc(c[2])}</span></div>`).join('');
    return `<tr class="prow" data-i="${i}">
        <td><b>${esc(e.symbol)}</b><span class="ph-only">${e.react_ok ? ' 🚀' : ''}</span>${P.added.includes(e.symbol) ? '<span class="badge">NEW</span>' : ''}${e.base_effect ? '<span class="badge warn">base</span>' : ''}<div class="muted ph-hide">${esc(e.sector || '')}</div><div class="muted ph-only">${dmy(e.res_date)} · ${e.score}/${e.checks.length}</div></td>
        <td class="ph-hide">${dmy(e.res_date)}<div class="muted">${Object.keys(e.series).length} ദിവസം</div></td>
        <td class="num ph-hide">${e.score}/${e.checks.length}</td>
        <td class="num">${tag}${e.g_yoy == null ? '—' : pct(e.g_yoy)}</td>
        <td class="num">${e.sue == null ? '—' : `<span class="${e.sue >= 2 ? 'up' : 'muted'}">${e.sue >= 2 ? '🔥 ' : ''}${e.sue.toFixed(1)}</span>`}</td>
        <td class="num ph-hide">${e.react == null ? '—' : (e.react_ok ? '🚀 ' : '') + pct(e.react)}${e.volx != null ? `<div class="muted">${e.volx.toFixed(1)}× vol</div>` : ''}</td>
        <td class="num"><b>${pct(n)}</b></td><td class="num col-wide">${pct(mx)}</td><td class="col-wide">${strip(e)}</td></tr>
      <tr class="pdet" data-i="${i}" hidden><td colspan="9"><div class="tiles">${tiles}</div><div class="days">${days}</div><div class="cklist">${checks}</div></td></tr>`;
  });
  h += `<div class="card"><div class="phead"><h2>📢 റിസൾട്ടിന് ശേഷം (${act.length})</h2>
    <label class="psort">ക്രമം <select id="psort">
      <option value="now">ഇപ്പോഴത്തെ %</option><option value="max">Max %</option><option value="sue">SUE</option><option value="score">Score</option>
      <option value="growth">Profit വളർച്ച</option><option value="react">പ്രതികരണം</option><option value="date">റിസൾട്ട് തീയതി</option><option value="symbol">പേര്</option></select></label></div>` +
    tvButtons(act) + `<div class="table-wrap"><table class="ptable"><thead><tr>${head}</tr></thead><tbody>${rows.join('')}</tbody></table></div></div>`;
  if (P.done.length) h += `<div class="card"><h2>✅ 60 ദിവസം പൂർത്തിയായവ</h2>` + table('<th>Stock</th><th>Result</th><th class="num">അവസാനം</th><th class="num">Max</th>',
      P.done.slice().reverse().map(e => `<tr><td><b>${esc(e.symbol)}</b></td><td>${dmy(e.res_date)}</td><td class="num">${pct(now(e))}</td><td class="num">${pct(best(e))}</td></tr>`)) + `</div>`;
  const W = (P.works || []).filter(w => w.n);
  if (W.length) {
    const cell = x => x && x.avg != null ? `<span class="${x.avg >= 0 ? 'up' : 'down'}">${x.avg >= 0 ? '+' : ''}${x.avg}%</span><br><small class="muted" title="ജയം % · എണ്ണം">${x.win}%·${x.n}</small>` : '<span class="muted">—</span>';
    h += `<div class="card"><h2>🔬 എന്താണ് ഫലിക്കുന്നത്</h2><p class="muted">ലാഭം കൂടിയ എല്ലാ റിസൾട്ടുകളും (Excellent അല്ലാത്തവയും) രേഖപ്പെടുത്തി, റിസൾട്ടിന് ശേഷം 5 / 20 / 60 ട്രേഡിംഗ് ദിവസത്തിലെ ശരാശരി റിട്ടേൺ. താഴെ ചെറുതായി: ജയിച്ച % · എണ്ണം. ആഴ്ചകൾ കഴിയുമ്പോൾ ഡാറ്റ നിറയും. Excellent ഗ്രൂപ്പ് മറ്റുള്ളവയേക്കാൾ മുന്നിലാണോ എന്നതാണ് പ്രധാനം.</p>` +
      table('<th>ഗ്രൂപ്പ്</th><th class="num ph-hide">എണ്ണം</th><th class="num">D5</th><th class="num">D20</th><th class="num">D60</th>',
        W.map(w => `<tr><td>${esc(w.g)}</td><td class="num ph-hide">${w.n}</td><td class="num">${cell(w.d5)}</td><td class="num">${cell(w.d20)}</td><td class="num">${cell(w.d60)}</td></tr>`)) + `</div>`;
  }
  document.getElementById('sbody').innerHTML = h;
  const setSort = (k, asc) => { try { localStorage.setItem('pead-sort', k); localStorage.setItem('pead-asc', asc ? '1' : '0'); } catch (e) {} renderPead(); };
  const sel = document.getElementById('psort');
  sel.value = sortBy;
  sel.addEventListener('change', () => setSort(sel.value, sel.value === 'symbol'));
  document.querySelectorAll('.ptable th.sortable').forEach(th => th.addEventListener('click', () => {
    const k = th.dataset.k; setSort(k, k === sortBy ? !sortAsc : k === 'symbol');
  }));
  document.querySelectorAll('.ptable .prow').forEach(tr => tr.addEventListener('click', () => {
    const d = document.querySelector(`.ptable .pdet[data-i="${tr.dataset.i}"]`); d.hidden = !d.hidden; tr.classList.toggle('open', !d.hidden);
  }));
  wireTv(act.map(e => e.symbol), `PEAD_${R.date}.txt`);
}
function render() {
  document.querySelectorAll('.tabs button').forEach(b => b.setAttribute('aria-selected', b.dataset.t === tab));
  if (tab === 'pead') return renderPead();
  const d = R[tab], cap = R.caps[tab], max = R.max_pos[tab];
  const fl = [...new Map(d.rows.flatMap(r => r.filters).map(x => [x.k, x.label])).entries()];
  const gateTxt = cap === 0 ? `<span class="no">പുതിയ entry ഇല്ല</span>` : cap < max ? `പരമാവധി ${cap} പൊസിഷൻ` : `പരമാവധി ${max} പൊസിഷൻ`;
  const extra = tab === 'value' && !R.have_val ? '<p class="muted">⚠️ Valuation (Gangil\'s 3) ഡാറ്റ ഇതുവരെ ബന്ധിപ്പിച്ചിട്ടില്ല — ഇപ്പോൾ ROE/EPS + 200 DMA മാത്രം.</p>' : '';
  const rows = d.rows.map(r => ({ ...r, st: status(r) }));
  const buy = rows.filter(r => r.st === 'buy'), watch = rows.filter(r => r.st === 'watch');
  const closed = d.closed.slice().reverse();
  const wins = d.closed.filter(c => (c.ret ?? 0) > 0).length;
  const extraCol = tab === 'momentum' ? '<th class="num">Rank</th>' : '<th class="num">vs 200 DMA</th>';
  const extraVal = r => tab === 'momentum' ? `<td class="num">${r.rank ?? '—'}</td>` : `<td class="num">${pct(r.prem200 == null ? null : r.prem200 * 100)}</td>`;
  let h = `<div class="card"><div class="kpi">
      <span>Market status <b>${esc(R.mstatus ? R.mstatus.name : '—')}</b></span>
      <span class="gate">${gateTxt}</span>
      <span>കൈവശം <b>${d.open.length}</b></span>
      <span>Buy ready <b>${buy.length}</b></span>
      <span>അടച്ച ട്രേഡ് <b>${d.closed.length}</b>${d.closed.length ? ` · ജയം ${Math.round(100 * wins / d.closed.length)}%` : ''}</span>
    </div>${extra}</div>`;
  if (d.entries.length || d.exits.length) {
    h += `<div class="card"><h2>🔔 ഇന്ന്</h2>` +
      (d.entries.length ? `<p>🟢 <b>Entry:</b> ${d.entries.map(p => `${esc(p.symbol)} @ ${num(p.entry)}`).join(', ')}</p>` : '') +
      (d.exits.length ? `<p>🚪 <b>Exit:</b> ${d.exits.map(p => `${esc(p.symbol)} @ ${num(p.exit)} (${pct(p.ret)}) — ${esc(p.reason)}`).join('; ')}</p>` : '') + `</div>`;
  }
  h += `<div class="card"><h2>📂 Model portfolio (${d.open.length})</h2>` + table(
    '<th>Stock</th><th class="num">Entry</th><th class="num">Now</th><th class="num">%</th><th class="col-wide">From</th>',
    d.open.map(p => `<tr><td><b>${esc(p.symbol)}</b><div class="muted">${esc(p.sector || '')}</div></td><td class="num">${num(p.entry)}</td><td class="num">${num(p.last)}</td><td class="num">${pct(p.last && p.entry ? (p.last / p.entry - 1) * 100 : null)}</td><td class="col-wide">${esc(p.entry_date)}</td></tr>`)) + `</div>`;
  h += `<div class="card"><h2>✅ Buy ready (${buy.length})</h2>` +
    (buy.length ? `<div class="tvbtns"><button type="button" id="tv-copy">📋 Copy to TradingView</button><button type="button" id="tv-file">⬇️ .txt (Import list)</button><span class="muted" id="tv-msg"></span></div>` : '') +
    `<p class="muted">എല്ലാ ഫിൽറ്ററും കടന്നവ. ഫിൽറ്റർ ഓഫ് ചെയ്ത് നോക്കാം:</p><div class="flt">` +
    fl.map(([k, l]) => `<label><input type="checkbox" data-k="${k}" ${off[tab].has(k) ? '' : 'checked'}> ${esc(l)}</label>`).join('') + `</div>` +
    table(`<th>Stock</th>${extraCol}<th class="num">Close</th><th>ഫിൽറ്റർ</th>`,
      buy.map(r => `<tr><td><b>${esc(r.symbol)}</b>${r.held ? '<span class="badge">കൈവശം</span>' : ''}<div class="muted">${esc(r.sector || '')}</div></td>${extraVal(r)}<td class="num">${num(r.close)}</td><td class="ok" title="${esc(r.filters.map(x => x.label + ': ' + x.note).join(' · '))}">✓ ${r.filters.filter(x => !off[tab].has(x.k)).length}/${r.filters.filter(x => !off[tab].has(x.k)).length}</td></tr>`)) + `</div>`;
  h += `<div class="card"><h2>👀 Watch (${watch.length})</h2><p class="muted">ഒന്നോ രണ്ടോ ഫിൽറ്റർ മാത്രം ബാക്കി — ബാക്കിയുള്ളത് ✗</p>` +
    table(`<th>Stock</th>${extraCol}<th class="num">Close</th><th>ബാക്കി</th>`,
      watch.map(r => `<tr><td><b>${esc(r.symbol)}</b>${r.held ? '<span class="badge">കൈവശം</span>' : ''}<div class="muted">${esc(r.sector || '')}</div></td>${extraVal(r)}<td class="num">${num(r.close)}</td><td class="wrap">${flags(r, true)}</td></tr>`)) + `</div>`;
  h += `<div class="card"><h2>📜 അടച്ച ട്രേഡുകൾ</h2>` + table(
    '<th>Stock</th><th class="num">%</th><th>കാരണം</th><th class="col-wide">തീയതി</th>',
    closed.map(c => `<tr><td><b>${esc(c.symbol)}</b></td><td class="num">${pct(c.ret)}</td><td class="wrap">${esc(c.reason)}</td><td class="col-wide">${esc(c.entry_date)} → ${esc(c.exit_date)}</td></tr>`)) + `</div>`;
  document.getElementById('sbody').innerHTML = h;
  wireTv(buy.map(r => r.symbol), `${tab === 'momentum' ? 'Momentum' : 'Value'}_BuyReady_${R.date}.txt`);
  document.querySelectorAll('.flt input').forEach(cb => cb.addEventListener('change', () => {
    cb.checked ? off[tab].delete(cb.dataset.k) : off[tab].add(cb.dataset.k); render();
  }));
}
document.querySelectorAll('.tabs button').forEach(b => b.addEventListener('click', () => {
  tab = b.dataset.t; try { localStorage.setItem('strat-tab', tab); } catch (e) {} render();
}));
render();
"""

STRAT_RULES = """
<details class="card"><summary><b>📖 നിയമങ്ങൾ</b></summary>
<h3>🚀 Momentum</h3>
<p><b>Candidates:</b> GM Universe-ലും Top MSWING ആദ്യ 100-ലും ഉള്ളവ.</p>
<ul><li><b>Stable rank:</b> കഴിഞ്ഞ 5 സെഷനിൽ 3 ദിവസമെങ്കിലും Top 100-ൽ</li>
<li><b>Trend:</b> Close &gt; 50 DMA &gt; 200 DMA</li>
<li><b>Not extended:</b> 20 EMA-യിൽ നിന്ന് 15%-ൽ കൂടുതൽ മുകളിൽ അല്ല</li>
<li><b>No results soon:</b> 7 ദിവസത്തിൽ റിസൾട്ട് ഇല്ല</li>
<li><b>Strong sector:</b> Landry momentum-ൽ മുകളിലെ പകുതി</li></ul>
<p><b>Exit:</b> 50 DMA-ക്ക് താഴെ 2 ദിവസം · 3 ദിവസമായി Top 100-ൽ ഇല്ല · 10% stop-loss</p>
<h3>💎 Value</h3>
<p><b>Candidates:</b> ROE/EPS IMPROVING സ്കാനർ.</p>
<ul><li><b>Margin of safety:</b> Fair Value-നേക്കാൾ 20% താഴെ (valuation ഡാറ്റ ഉള്ളപ്പോൾ). Fair Value-ന് മുകളിലുള്ളവ (overvalued) Watch-ലും കാണിക്കില്ല</li>
<li><b>Few red flags:</b> Screener Excel-ലെ 8 red flag പരിശോധനയിൽ 1-ൽ കൂടുതൽ ചുവപ്പ് ഇല്ല (value trap ഒഴിവാക്കാൻ)</li>
<li><b>5Y quality:</b> 5 വർഷത്തെ sales / profit / net worth / ROCE പരിശോധനയിൽ 4-ൽ 3 എണ്ണമെങ്കിലും പാസ്</li>
<li><b>Stable in scanner:</b> കഴിഞ്ഞ 5 സെഷനിൽ 3 ദിവസമെങ്കിലും സ്കാനറിൽ</li>
<li><b>Above 200 DMA</b></li>
<li><b>Near 200 DMA:</b> 200 DMA-യിൽ നിന്ന് 20%-നുള്ളിൽ (അധികം ഉയർന്നത് വേണ്ട)</li></ul>
<p><b>Exit:</b> Intrinsic value എത്തി · 200 DMA-ക്ക് 10%-ൽ കൂടുതൽ താഴെ · 3 ദിവസമായി സ്കാനറിൽ ഇല്ല</p>
<h3>📢 PEAD (Post-Earnings Announcement Drift)</h3>
<p>Excellent റിസൾട്ട് വന്ന സ്റ്റോക്കുകൾ, റിസൾട്ട് ദിവസം മുതൽ ഓരോ ദിവസവും എത്ര % മാറി എന്ന ട്രാക്കർ (buy/sell നിയമങ്ങൾ ഇല്ല). Excellent = 7 പരിശോധനയിൽ 5 എണ്ണമെങ്കിലും, ആദ്യ 3 നിർബന്ധം:</p>
<ul><li><b>EPS growth</b> ≥30% YoY (Chartink-ൽ ക്വാർട്ടർ EPS ഇല്ല — ക്വാർട്ടർ net profit growth)</li><li><b>Sales growth</b> ≥15% YoY</li>
<li><b>Quality of earnings:</b> core profit (PBT − other income) YoY ≥20% — other income / ഒറ്റത്തവണ നേട്ടം കൊണ്ടുള്ള ലാഭം ഒഴിവാക്കാൻ</li>
<li><b>Acceleration:</b> ഈ ക്വാർട്ടറിലെ YoY growth മുൻ ക്വാർട്ടറിനേക്കാൾ കൂടുതൽ</li><li><b>QoQ growth:</b> profit മുൻ ക്വാർട്ടറിനേക്കാൾ കൂടുതൽ</li>
<li><b>Record quarter:</b> 5 ക്വാർട്ടറിലെ ഉയർന്ന profit</li><li><b>Real growth:</b> ഒരു വർഷം മുമ്പും ലാഭത്തിൽ (low base അല്ല)</li></ul>
<p><b>ലേബലുകൾ (Excellent തീരുമാനിക്കുന്നതിൽ ഇല്ല):</b> <b>SUE</b> = ഈ ക്വാർട്ടറിലെ YoY profit മാറ്റം കമ്പനിയുടെ കഴിഞ്ഞ 8 ക്വാർട്ടറിലെ സാധാരണ മാറ്റത്തേക്കാൾ എത്ര standard deviation കൂടുതൽ (2+ = വലിയ surprise) · <b>പ്രതികരണം</b> = റിസൾട്ട് ദിവസത്തെ / പിറ്റേന്നത്തെ വില % + volume · <b>Margin</b> = core EBITDA margin മുൻ വർഷത്തെ അതേ ക്വാർട്ടറുമായി · <b>വളർച്ച</b> = profit YoY %, നില: 150%+ ശരിക്കും വലിയ വളർച്ച · 75–150% ശക്തം · 30–75% മാന്യമായ വളർച്ച · base effect ഉള്ളവയ്ക്ക് 2 വർഷം മുമ്പുമായുള്ള താരതമ്യം വെച്ച് (20%-ന് താഴെ = വെറും തിരിച്ചുവരവ്) · <b>base effect</b> = profit 150%+ വളർന്നത് (മുൻ വർഷം ലാഭം കുറവ്) — അതിന് താഴെ 2 വർഷം മുമ്പത്തെ അതേ ക്വാർട്ടറുമായുള്ള താരതമ്യം: അതും ശക്തമാണെങ്കിൽ യഥാർത്ഥ വളർച്ച, കുറവാണെങ്കിൽ വെറും തിരിച്ചുവരവ്.</p>
<p class="muted">റിസൾട്ട് തീയതി NSE കലണ്ടറിൽ നിന്ന്. Chartink പുതിയ ക്വാർട്ടർ ചേർത്ത ശേഷം മാത്രം പരിശോധിക്കും (സാധാരണ റിസൾട്ടിന് പിറ്റേന്ന്). % = റിസൾട്ടിന് തൊട്ടുമുമ്പുള്ള ട്രേഡിംഗ് ദിവസത്തെ close-ൽ നിന്ന്.</p>
<h3>🧭 Market status gate</h3>
<p>Momentum: Stay out / Failed turn / Wait → പുതിയ entry ഇല്ല; Bottoming / Early rally → പരമാവധി 3. Value: Stay out → പുതിയ entry ഇല്ല. ബാക്കി → പരമാവധി 10.</p>
<p class="muted">Model portfolio: Buy ready ആയ സ്റ്റോക്ക് അന്നത്തെ close-ൽ "വാങ്ങിയതായി" കണക്കാക്കും. Strategy എങ്ങനെ പ്രവർത്തിക്കുന്നു എന്ന് നോക്കാനാണ്, യഥാർത്ഥ portfolio അല്ല.</p>
</details>
"""


def _conviction_html(conv):
    if not conv:
        return ""
    rows = "".join(
        f'<tr><td><b>{_e(d["symbol"])}</b><br><small class="muted">{_e("" if (d.get("sector") or "") == "Unknown" else d.get("sector") or "")}</small></td>'
        f'<td class="num"><b>{d["score"]}</b></td><td style="white-space:normal">' + "".join(f'<span class="chip">{_e(x)}</span>' for x in d["src"]) + "</td></tr>"
        for d in conv)
    return ('<div class="card conv"><style>.conv td{white-space:normal;vertical-align:top}.conv .chip{font-size:.75rem;margin:2px 3px 2px 0}</style><h2 style="margin:0 0 4px">⭐ Top conviction</h2>'
            '<p class="muted" style="margin:0 0 8px">പല strategy-കളിലും ഒരേ സമയം വരുന്ന സ്റ്റോക്കുകൾ — '
            'Momentum/Value Buy = 2, Watch = 1, PEAD = 1 (🔥 = 2), HOLYGRAIL / MULTIBAGGER = 1. കുറഞ്ഞത് 2 സ്രോതസ്സ്.</p>'
            '<div style="overflow-x:auto"><table class="ptable"><thead><tr><th>Stock</th><th class="num">Score</th><th>എവിടെയെല്ലാം</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></div>')


def build_strategy(out_dir, res):
    if not res:
        return
    out = Path(out_dir)
    data = json.dumps(res, ensure_ascii=False, default=str).replace("</", "<\\/")
    body = (
        '<p><a href="index.html">← എല്ലാ റിപ്പോർട്ടുകളും</a></p>'
        "<h1>📋 Stock selection strategy</h1>"
        f'<p class="muted">{_e(nice_date(res["date"]))} · വില കിട്ടിയത് {res["prices"]} സ്റ്റോക്ക് · ഇത് സാമ്പത്തിക ഉപദേശമല്ല</p>'
        + _conviction_html(res.get("conviction"))
        + '<div class="tabs" role="tablist"><button type="button" data-t="momentum">🚀 Momentum</button>'
        '<button type="button" data-t="value">💎 Value</button>'
        '<button type="button" data-t="pead">📢 PEAD</button></div>'
        '<div id="sbody"></div>' + STRAT_RULES
        + f'<script type="application/json" id="sdata">{data}</script><script>{STRAT_JS}</script>'
    )
    page = _page("Strategy", body).replace("</style>", STRAT_CSS + "</style>", 1)
    (out / "strategy.html").write_text(page, encoding="utf-8")
    _write_index(out)
