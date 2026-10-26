"""AI-യോട് സംസാരിക്കുന്ന ഭാഗം — ഇതാണ് മാറ്റാവുന്ന "പ്ലഗ്".

AI_PROVIDERS എന്ന setting-ലെ ക്രമത്തിൽ ശ്രമിക്കും (ഡിഫോൾട്ട്: gemini,groq).
ഒന്ന് പരാജയപ്പെട്ടാൽ (key ഇല്ല, പരിധി കഴിഞ്ഞു, സെർവർ പ്രശ്നം) അടുത്തതിലേക്ക് പോകും.
പുതിയ AI ചേർക്കാൻ: ഒരു ഫംഗ്ഷൻ എഴുതി PROVIDERS-ൽ ചേർത്താൽ മതി.

search=True ആണെങ്കിൽ AI ഇന്റർനെറ്റിൽ വാർത്ത തിരഞ്ഞ് ഉത്തരം എഴുതും
(Gemini: Google Search grounding, Groq: web search ഉള്ള "compound" മോഡൽ).
"""
import os
import time

import requests


def _env(name, default):
    return (os.environ.get(name) or "").strip() or default


def _gemini(system, prompt, search=False):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY ഇല്ല")
    model = _env("GEMINI_MODEL", "gemini-flash-latest")
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4},
    }
    if search:
        body["tools"] = [{"google_search": {}}]
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json=body,
        timeout=180,
    )
    _check(r)
    parts = r.json()["candidates"][0]["content"]["parts"]
    label = f"Gemini ({model}{' + Google Search' if search else ''})"
    return "".join(p.get("text", "") for p in parts).strip(), label


def _groq(system, prompt, search=False):
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GROQ_API_KEY ഇല്ല")
    model = _env("GROQ_SEARCH_MODEL", "groq/compound") if search else _env("GROQ_MODEL", "openai/gpt-oss-120b")
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "temperature": 0.4,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=180,
    )
    _check(r)
    label = f"Groq ({model}{' + web search' if search else ''})"
    return r.json()["choices"][0]["message"]["content"].strip(), label


PROVIDERS = {"gemini": _gemini, "groq": _groq}


class RetryableError(RuntimeError):
    pass


def _check(r):
    if r.status_code == 429 or r.status_code >= 500:
        raise RetryableError(f"HTTP {r.status_code}: {r.text[:200]}")
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")


def generate(system, prompt, search=False):
    """റിപ്പോർട്ട് ടെക്സ്റ്റും ഉപയോഗിച്ച AI-യുടെ പേരും തിരികെ തരും."""
    order = [p.strip().lower() for p in _env("AI_PROVIDERS", "gemini,groq").split(",") if p.strip()]
    errors = []
    for name in order:
        fn = PROVIDERS.get(name)
        if not fn:
            errors.append(f"{name}: അറിയാത്ത provider")
            continue
        for attempt in (1, 2):
            try:
                text, label = fn(system, prompt, search)
                if text:
                    return text, label
                raise RuntimeError("ശൂന്യമായ മറുപടി")
            except RetryableError as e:
                if attempt == 1:
                    time.sleep(8)
                    continue
                errors.append(f"{name}: {e}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"{name}: {e}")
                break
    raise RuntimeError("എല്ലാ AI-യും പരാജയപ്പെട്ടു → " + " | ".join(errors))
