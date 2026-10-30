"""റിപ്പോർട്ടിന്റെ രൂപം (മാതൃക 1) — Telegram മെസേജും വെബ്‌പേജിനുള്ള ഡാറ്റയും ഇവിടെ ഉണ്ടാക്കുന്നു.

ഘടന കോഡ് തന്നെ ഉണ്ടാക്കുന്നതിനാൽ എല്ലാ ദിവസവും ഒരേ ക്രമത്തിൽ, വൃത്തിയായി വരും.
AI തരുന്നത് രണ്ട് കാര്യം മാത്രം: ചുരുക്കം (summary), ഓരോ സ്റ്റോക്കിന്റെയും കാരണം (reasons).
"""
import html
import json
import re
from datetime import date

DAYS = ["തിങ്കൾ", "ചൊവ്വ", "ബുധൻ", "വ്യാഴം", "വെള്ളി", "ശനി", "ഞായർ"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
RULE = "━━━━━━━━━━━━━━━━"
NO_NEWS = "വ്യക്തമായ വാർത്തയില്ല"


def e(s):
    return html.escape(str(s), quote=False)


def nice_date(ds):
    d = date.fromisoformat(ds)
    return f"{d.day} {MONTHS[d.month - 1]}, {DAYS[d.weekday()]}"


def short_date(ds):
    d = date.fromisoformat(ds)
    return f"{d.day} {MONTHS[d.month - 1]}"


def short_name(scan):
    return scan["name"].split(" (")[0]


# ---------- AI മറുപടി ----------

def parse_ai(text):
    """AI-യുടെ JSON മറുപടി വായിക്കും. JSON അല്ലെങ്കിൽ ടെക്സ്റ്റ് മുഴുവൻ ചുരുക്കമായി എടുക്കും."""
    out = {"summary": "", "reasons": {}, "sectors": {}}
    if not text:
        return out
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            out["summary"] = str(d.get("summary") or "").strip()
            out["reasons"] = {str(k).upper(): str(v).strip() for k, v in (d.get("reasons") or {}).items() if v}
            out["sectors"] = {str(k): str(v).strip() for k, v in (d.get("sectors") or {}).items() if v}
            return out
        except (ValueError, AttributeError):
            pass
    plain = re.sub(r"[#*`]+", "", text)
    out["summary"] = re.sub(r"\n{2,}", "\n", plain).strip()[:700]
    return out


# ---------- ശ്രദ്ധിക്കേണ്ട സ്റ്റോക്കുകൾ ----------

def notable_rows(scans, symbols, ai, results):
    """symbols ക്രമത്തിൽ: ഏതൊക്കെ സ്കാനറിൽ, സെക്ടർ, വില, കാരണം."""
    info, where = {}, {}
    for s in scans:
        for x in s["stocks"]:
            info.setdefault(x["symbol"], x)
            where.setdefault(x["symbol"], []).append(short_name(s) + ("🆕" if x["symbol"] in s.get("new", []) else ""))
    rows = []
    for sym in symbols:
        x = info.get(sym)
        if not x:
            continue
        rows.append({"symbol": sym, "scanners": where.get(sym, []), "sector": x.get("sector", ""),
                     "close": x.get("close"), "change": x.get("change"),
                     "reason": ai["reasons"].get(sym.upper(), ""), "results": results.get(sym)})
    return rows


# ---------- Telegram (HTML) ----------

def telegram_daily(date_str, sig, fresh, scans, rows, sector_rows, bmoves, results_key, results_total,
                   ai, ai_label, link, strategy_text="", strategy_link="", action_text=""):
    L = [f"📊 <b>മാർക്കറ്റ് റിപ്പോർട്ട്</b> · {e(nice_date(date_str))}", RULE]
    if action_text:
        L.append("✅ <b>ഇന്നത്തെ action</b>")
        L.extend(e(x) for x in action_text.splitlines())
        L.extend([RULE])

    if sig:
        L.append(f"{sig['emoji']} <b>മാർക്കറ്റ്: {e(sig['label'])}</b> · {e(sig['trend'])}")
        L.append(f"20: {sig['t20']:.0f} · 50: {sig['t50']:.0f} · 200: {sig['t200']:.0f} · NH-NL {sig['nh']:+.1f}%")
        if not fresh:
            L.append(f"<i>({e(sig['asOf'])}-ലെ ബ്രെഡ്ത്ത് — ഇന്നത്തേത് വന്നില്ല)</i>")
        L.append("")
        ms = sig.get("mstat")
        if ms:
            c = ms["cycle"]
            L.append(f"🧭 <b>Market status: {e(ms['name'])}</b> {ms['emoji']}")
            L.append(f"Cycle: {e(c['cond'])} ({c['n']}/{c['tot']}) · Sentiment: {e(ms['sentiment'])}")
            L.append(f"<code>" + e("  ".join(f"{t['ma']}: {t['state']}" for t in c["tfs"])) + "</code>")
            L.append(f"Breadth {e(ms['breadth'])} · MSWING {e(ms['momentum'])}")
            L.append(f"<i>{e(ms['meaning'])}</i>")
            L.append("")

    L.append("🎯 <b>സിഗ്നലുകൾ</b>")
    width = max((len(short_name(s)) for s in scans), default=10)
    for s in scans:
        name = short_name(s)
        if s.get("error"):
            L.append(f"<code>{e(name.ljust(width))}   —</code> ⚠️ പിശക്")
            continue
        n, new = len(s["stocks"]), s.get("new", [])
        line = f"<code>{e(name.ljust(width))} {n:>4}</code>"
        if s.get("max_show"):
            line += f"  🆕 {len(new)}" if new else ""
        elif n:
            ordered = sorted(s["stocks"], key=lambda x: (x["symbol"] not in new, -(x["change"] or 0)))
            syms = [x["symbol"] + ("🆕" if x["symbol"] in new else "") for x in ordered[:8]]
            line += "  " + e(", ".join(syms)) + (" …" if n > 8 else "")
        L.append(line)
    L.append("")

    for s in scans:
        if s.get("ranked") and s["stocks"] and not s.get("error"):
            L += ranked_section(s)
            L.append("")

    if rows:
        L.append("⭐ <b>ശ്രദ്ധിക്കേണ്ടവ</b>")
        for r in rows[:6]:
            if r["reason"]:
                reason = r["reason"]
            else:
                bits = [b for b in (r["sector"] if r["sector"] != "Unknown" else "",
                                    f"{r['change']:+.1f}%" if r["change"] is not None else "") if b]
                reason = ", ".join(bits) or "—"
            warn = f" ⚠️റിസൾട്ട് {e(short_date(r['results']))}" if r["results"] else ""
            L.append(f"• <b>{e(r['symbol'])}</b> – {e(reason)}{warn}")
        L.append("")

    sec_bits = []
    known = [x for x in sector_rows if x["sector"] != "Unknown"][:3]
    if known:
        sec_bits.append("സ്കാനറുകളിൽ മുന്നിൽ: " + e(", ".join(f"{x['sector']} {x['count']}" for x in known)))
    if bmoves:
        up = ", ".join(x["sector"] for x in bmoves["gainers"][:3])
        dn = ", ".join(x["sector"] for x in bmoves["losers"][:3])
        if up or dn:
            sec_bits.append(f"↑ {e(up or '—')}    ↓ {e(dn or '—')}")
    if sec_bits:
        L.append("🏭 <b>സെക്ടർ</b>")
        L += sec_bits
        L.append("")

    if results_total:
        shown = list(results_key.items())[:8]
        txt = ", ".join(f"{k} {short_date(v)}" for k, v in shown) or "സിഗ്നൽ സ്കാനറുകളിൽ ഇല്ല"
        extra = results_total - len(shown)
        if extra > 0:
            txt += f" · വലിയ ലിസ്റ്റുകളിൽ {extra} എണ്ണം"
        L.append(f"⚠️ <b>റിസൾട്ട് (7 ദിവസം)</b>: {e(txt)}")
        L.append("")

    if ai["summary"]:
        L.append("💡 <b>ചുരുക്കം</b>")
        L.append(e(ai["summary"]))
        L.append("")

    if strategy_text:
        L.append("📋 <b>Strategy</b>")
        L.append(e(strategy_text))
        if strategy_link:
            L.append(f'<a href="{e(strategy_link)}">Buy ready / Watch / Exit പട്ടിക</a>')
        L.append("")

    if link:
        L.append(f'🔗 <a href="{e(link)}">മുഴുവൻ റിപ്പോർട്ട്</a> · 📄 PDF താഴെ')
    L.append(f"<i>{e(ai_label)} · ഇത് സാമ്പത്തിക ഉപദേശമല്ല</i>")
    return "\n".join(L)


def ranked_section(s, show=10):
    new = set(s.get("new", []))
    top = sorted(s["stocks"], key=lambda x: x["rank"])
    out = [f"🚀 <b>{e(short_name(s))} · Top {len(top)}</b>"]
    rows = []
    for x in top[:show]:
        sc = f"{x['score']:.1f}" if x.get("score") is not None else "—"
        mark = "🆕" if x["symbol"] in new else ""
        mv = ""
        if x.get("rank_up"):
            mv = f" ↑{x['rank_up']}" if x["rank_up"] > 0 else f" ↓{-x['rank_up']}"
        rows.append(f"<code>{x['rank']:>2}. {e(x['symbol'][:12].ljust(12))} {sc:>6}</code>{mark}{e(mv)}")
    out += rows
    if len(top) > show:
        out.append(f"<i>… #{show + 1}–{len(top)} വെബ്‌സൈറ്റിൽ</i>")
    window = len(s.get("ranks") or {}) or 100
    climbers = sorted((x for x in top[show:] if (x.get("rank_up") or 0) >= 5), key=lambda x: -x["rank_up"])[:4]
    if climbers:
        bits = [f"{x['symbol']} #{x['prev_rank'] or str(window) + '+'}→#{x['rank']}" for x in climbers]
        out.append(f"📈 #{show + 1}–{len(top)}-ൽ മുന്നേറിയവ: " + e(", ".join(bits)))
    return out


def md_to_telegram(md):
    """ആഴ്ച റാപ്പപ്പിലെ AI Markdown → Telegram HTML (## തലക്കെട്ട് ബോൾഡ്, - ലിസ്റ്റ് •)."""
    out = []
    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            if out and out[-1] != "":
                out.append("")
            continue
        h = re.match(r"^\s*#{1,6}\s+(.*)", line)
        b = re.match(r"^\s*[-*•]\s+(.*)", line)
        if h:
            txt = re.sub(r"\*\*(.+?)\*\*", r"\1", h.group(1))
            if out and out[-1] != "":
                out.append("")
            out.append(f"<b>{e(txt)}</b>")
            continue
        body = b.group(1) if b else line
        body = re.sub(r"\*\*(.+?)\*\*", lambda m: "\x00" + m.group(1) + "\x01", body)
        body = e(body).replace("\x00", "<b>").replace("\x01", "</b>")
        out.append(("• " if b else "") + body)
    return "\n".join(out).strip()


def to_discord(tg_html):
    """Telegram HTML → Discord Markdown."""
    t = re.sub(r'<a href="([^"]+)">([^<]+)</a>', r"\2: \1", tg_html)
    t = t.replace("<b>", "**").replace("</b>", "**").replace("<i>", "*").replace("</i>", "*")
    t = t.replace("<code>", "`").replace("</code>", "`")
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t)
