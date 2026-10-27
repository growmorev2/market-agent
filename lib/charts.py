"""GM World ബ്രെഡ്ത്ത് ഗ്രാഫുകൾ (SVG) — വെബ്‌പേജിലും PDF-ലും Telegram ചിത്രത്തിലും ഉപയോഗിക്കുന്നു.

ഗ്രാഫ് 1: 20 / 50 / 200 DMA-ക്ക് മുകളിലുള്ള സ്റ്റോക്കുകളുടെ % (0–100), GM World സോണുകൾ (20, 50, 80)
ഗ്രാഫ് 2: Net New Highs − New Lows % (പൂജ്യത്തിന് മുകളിൽ നീല, താഴെ ചുവപ്പ്)
"""
import html

INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SERIES = [("t20", "Short 20", "#2a78d6"), ("t50", "Medium 50", "#eb6834"), ("t200", "Long 200", "#1baf7a")]
POS, NEG = "#2a78d6", "#e34948"
FONT = "font-family=\"'Noto Sans Malayalam','Noto Sans',system-ui,sans-serif\""


def _e(s):
    return html.escape(str(s))


def _ticks(dates, n=5):
    if len(dates) <= n:
        return list(range(len(dates)))
    step = (len(dates) - 1) / (n - 1)
    return sorted({round(i * step) for i in range(n)})


def breadth_lines(data, sessions=20, w=640, h=260):
    k = min(sessions, len(data["dates"]))
    dates = data["dates"][-k:]
    L, R, T, B = 34, 92, 30, 28
    pw, ph = w - L - R, h - T - B
    x = lambda i: L + (pw * i / max(1, k - 1))
    y = lambda v: T + ph * (1 - max(0, min(100, v)) / 100)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" role="img" '
           f'aria-label="Percent of stocks above 20, 50 and 200 day averages" {FONT}>',
           f'<rect width="{w}" height="{h}" rx="10" fill="{SURFACE}"/>',
           f'<text x="{L}" y="18" font-size="13" font-weight="700" fill="{INK}">ബ്രെഡ്ത്ത്: DMA-ക്ക് മുകളിലുള്ള സ്റ്റോക്കുകൾ %</text>']
    for v, lab in ((20, "20"), (50, "50"), (80, "80")):
        out.append(f'<line x1="{L}" x2="{L + pw}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{GRID}" stroke-dasharray="3 4"/>')
        out.append(f'<text x="{L - 6}" y="{y(v) + 4:.1f}" font-size="10" text-anchor="end" fill="{MUTED}">{lab}</text>')
    out.append(f'<line x1="{L}" x2="{L + pw}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="{GRID}"/>')
    for i in _ticks(dates):
        out.append(f'<text x="{x(i):.1f}" y="{h - 9}" font-size="10" text-anchor="middle" fill="{MUTED}">{_e(dates[i])}</text>')
    # അവസാന ലേബലുകൾ കൂട്ടിമുട്ടാതിരിക്കാൻ ലംബമായി അകറ്റുന്നു
    ends = []
    for key, name, col in SERIES:
        vals = data[key][-k:]
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        out.append(f'<circle cx="{x(k - 1):.1f}" cy="{y(vals[-1]):.1f}" r="4" fill="{col}" stroke="{SURFACE}" stroke-width="2">'
                   f'<title>{_e(name)}: {vals[-1]:.1f}</title></circle>')
        ends.append([y(vals[-1]), name, vals[-1], col])
    ends.sort()
    for j in range(1, len(ends)):
        if ends[j][0] - ends[j - 1][0] < 14:
            ends[j][0] = ends[j - 1][0] + 14
    for yy, name, v, col in ends:
        out.append(f'<rect x="{L + pw + 8}" y="{yy - 5:.1f}" width="8" height="8" rx="2" fill="{col}"/>')
        out.append(f'<text x="{L + pw + 20}" y="{yy + 3:.1f}" font-size="11" fill="{INK}">{_e(name)} <tspan font-weight="700">{v:.0f}</tspan></text>')
    out.append("</svg>")
    return "".join(out)


def nhnl_bars(data, sessions=20, w=640, h=170):
    k = min(sessions, len(data["dates"]))
    dates, vals = data["dates"][-k:], data["nh"][-k:]
    L, R, T, B = 34, 92, 30, 28
    pw, ph = w - L - R, h - T - B
    lim = max(5, max(abs(v) for v in vals))
    y = lambda v: T + ph * (1 - (v + lim) / (2 * lim))
    slot = pw / k
    bw = max(3, slot - 2)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" role="img" '
           f'aria-label="Net new highs minus new lows percent" {FONT}>',
           f'<rect width="{w}" height="{h}" rx="10" fill="{SURFACE}"/>',
           f'<text x="{L}" y="18" font-size="13" font-weight="700" fill="{INK}">പുതിയ ഹൈ − പുതിയ ലോ (Net NH-NL %)</text>',
           f'<line x1="{L}" x2="{L + pw}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="{MUTED}"/>',
           f'<text x="{L - 6}" y="{y(0) + 4:.1f}" font-size="10" text-anchor="end" fill="{MUTED}">0</text>',
           f'<text x="{L - 6}" y="{y(lim) + 8:.1f}" font-size="10" text-anchor="end" fill="{MUTED}">+{lim:.0f}</text>',
           f'<text x="{L - 6}" y="{y(-lim):.1f}" font-size="10" text-anchor="end" fill="{MUTED}">−{lim:.0f}</text>']
    for i, v in enumerate(vals):
        x0 = L + i * slot + (slot - bw) / 2
        top, bot = (y(v), y(0)) if v >= 0 else (y(0), y(v))
        hgt = max(1.5, bot - top)
        r = min(3, bw / 2, hgt / 2)
        out.append(f'<rect x="{x0:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{hgt:.1f}" rx="{r:.1f}" '
                   f'fill="{POS if v >= 0 else NEG}"><title>{_e(dates[i])}: {v:+.1f}%</title></rect>')
    for i in _ticks(dates):
        out.append(f'<text x="{L + i * slot + slot / 2:.1f}" y="{h - 9}" font-size="10" text-anchor="middle" fill="{MUTED}">{_e(dates[i])}</text>')
    last = vals[-1]
    out.append(f'<text x="{L + pw + 8}" y="{y(last) + 4:.1f}" font-size="11" fill="{INK}">ഇന്ന് <tspan font-weight="700">{last:+.1f}%</tspan></text>')
    out.append("</svg>")
    return "".join(out)


def standalone_html(data):
    """Telegram-ന് ചിത്രമാക്കാനുള്ള ചെറിയ പേജ്."""
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<link href='https://fonts.googleapis.com/css2?family=Noto+Sans+Malayalam:wght@400;700&display=swap' rel='stylesheet'>"
            f"<style>body{{margin:0;background:#fff}}#c{{width:640px;padding:10px;display:grid;gap:10px}}</style></head>"
            f"<body><div id='c'>{breadth_lines(data)}{nhnl_bars(data)}</div></body></html>")
