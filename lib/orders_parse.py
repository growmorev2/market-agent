"""Order announcement ടെക്സ്റ്റിൽ നിന്ന് order value (₹ crore) കണ്ടെത്തൽ.

രീതി: ടെക്സ്റ്റിലെ തുകകളിൽ ആദ്യം വരുന്ന "ശരിയായ" തുക (order book, revenue, classification table
തുടങ്ങിയവ ഒഴിവാക്കി). ഒന്നും കിട്ടിയില്ലെങ്കിൽ None — പേജിൽ "value ഇല്ല" എന്ന് കാണിക്കും.
"""
import html
import re

USD_INR = 88.0
EUR_INR = 102.0
_NUM = r"(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)\+?"
_CUR = r"(₹|rs\.?|inr|rupees|usd|us\$|\$|eur|€)"
_UNIT = r"(crores?|crs?\b\.?|cr\b|lakhs?|lacs?|millions?|mn\b|mio\b|billions?|bn\b)"
PAT = re.compile(
    _CUR + r"\s*" + _NUM + r"\s*(?:/-)?\s*\*?\s*(?:" + _UNIT + r"|\(\s*rupees[a-z\s\-]*?(crores?|lakhs?)[^)]*\))?", re.I)
NEG = re.compile(r"order\s*book|backlog|turnover|revenue|multinational|net\s*worth|market\s*cap|year\s*to\s*date|\bytd\b|"
                 r"so\s*far|till\s*date|cumulative|total\s+amended|paid[\s-]*up|share\s*capital|tariff|per\s+unit|"
                 r"classification|inflow", re.I)
LT_CLASS = {"significant": 1000, "large": 2500, "major": 5000, "mega": 10000, "ultra-mega": 15000}


def _clean(text):
    t = html.unescape(text or "").replace("₹", "₹").replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"(\d), (\d{2,3})\b", r"\1,\2", t)   # "1, 006" → "1,006"
    t = re.sub(r"(\d) \.(\d)", r"\1.\2", t)         # "5 .25" → "5.25"
    return t


def _to_cr(num, unit, cur):
    v = float(num.replace(",", ""))
    u = (unit or "").lower().rstrip(".")
    if u.startswith("cr"):
        pass
    elif u.startswith("la"):
        v /= 100
    elif u.startswith("mi") or u in ("mn", "mio"):
        v /= 10
    elif u.startswith("bi") or u == "bn":
        v *= 100
    else:
        v /= 1e7  # absolute rupees
    c = (cur or "").lower()
    if c in ("usd", "us$", "$"):
        v *= USD_INR
    elif c in ("eur", "€"):
        v *= EUR_INR
    return v


def candidates(text):
    """[(₹ cr, നല്ലതാണോ, "total" എന്ന് മുമ്പിലുണ്ടോ)] ടെക്സ്റ്റിലെ ക്രമത്തിൽ."""
    t = _clean(text)
    out = []
    for m in PAT.finditer(t):
        cur, num, unit = m.group(1), m.group(2), m.group(3) or m.group(4)
        digits = len(num.replace(",", "").split(".")[0])
        if digits >= 7 and not m.group(3):
            unit = None  # Rs. 91,77,77,777/- (Rupees ... Crore ...) — സംഖ്യ തന്നെ മുഴുവൻ തുക
        if not unit and digits < 6:
            continue  # യൂണിറ്റ് ഇല്ലാത്ത ചെറിയ സംഖ്യ — തുകയല്ല
        try:
            v = _to_cr(num, unit, cur)
        except ValueError:
            continue
        if not (0.5 <= v <= 500000):
            continue
        before, after = t[max(0, m.start() - 110):m.start()], t[m.end():m.end() + 25]
        bad = bool(NEG.search(before)) or bool(re.match(r"[^.]{0,30}(multinational|conglomerate|group company)", after + t[m.end() + 25:m.end() + 40], re.I)) or re.match(r"\s*(?:to|-|–)\s*(?:rs\.?|₹|inr)?\s*\d", after, re.I) \
            or re.search(r"\bto\s*$", before, re.I)
        out.append((round(v, 2), not bad, bool(re.search(r"\btotal\b[^.]{0,40}$", before, re.I))))
    return out


def order_value(text, symbol=""):
    """(₹ crore, കുറിപ്പ്) — കുറിപ്പ്: "" / "range" (L&T പോലുള്ള classification) / None കിട്ടിയില്ല."""
    c = [x for x in candidates(text) if x[1]]
    tot = [v for v, _, t in c if t]
    if tot:      # "Total Lot 1 & Lot 2: Rs. 949 Cr" പോലെ — ആകെ തുക
        return max(tot), ""
    if c:
        return c[0][0], ""
    if symbol == "LT":
        t = _clean(text)
        m = re.search(r"orders?\s*\(\s*(ultra-mega|mega|major|large|significant)\*?\s*\)", t, re.I) or \
            re.search(r"\b(?:wins|secured|bags)\s+(ultra-mega|mega|major|large|significant)\b", t, re.I)
        if m:
            return float(LT_CLASS[m.group(1).lower()]), "range"
    return None, None


CONSORTIUM = re.compile(r"consortium|joint venture|\bJV\b|share of the company|company'?s share", re.I)
