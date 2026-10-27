"""AI-യോട് സംസാരിക്കുന്ന ഭാഗം — ഇതാണ് മാറ്റാവുന്ന "പ്ലഗ്".

AI_PROVIDERS എന്ന setting-ലെ ക്രമത്തിൽ ശ്രമിക്കും (ഡിഫോൾട്ട്: gemini,groq).
ഒന്ന് പരാജയപ്പെട്ടാൽ (key ഇല്ല, പരിധി കഴിഞ്ഞു, സെർവർ പ്രശ്നം) അടുത്തതിലേക്ക് പോകും.
പുതിയ AI ചേർക്കാൻ: ഒരു ഫംഗ്ഷൻ എഴുതി PROVIDERS-ൽ ചേർത്താൽ മതി.

search=True ആണെങ്കിൽ AI ഇന്റർനെറ്റിൽ വാർത്ത തിരഞ്ഞ് ഉത്തരം എഴുതും
(Gemini: Google Search grounding, Groq: gpt-oss മോഡലിന്റെ browser_search ടൂൾ).

Gemini: ഒരു മോഡലിന് സൗജന്യ പരിധി ഇല്ലെങ്കിൽ / കഴിഞ്ഞാൽ (429) അല്ലെങ്കിൽ മോഡൽ ഇല്ലെങ്കിൽ (404)
GEMINI_MODELS ലിസ്റ്റിലെ അടുത്ത മോഡൽ സ്വയം ശ്രമിക്കും.
"""
import os
import time

import requests


def _env(name, default):
    return (os.environ.get(name) or "").strip() or default


GEMINI_DEFAULTS = "gemini-3.8-flash,gemini-flash-latest,gemini-3.5-flash,gemini-3.5-flash-lite,gemini-flash-lite-latest"


def _gemini(system, prompt, search=False):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY ഇല്ല")
    single = (os.environ.get("GEMINI_MODEL") or "").strip()
    models = [single] if single else [m.strip() for m in _env("GEMINI_MODELS", GEMINI_DEFAULTS).split(",") if m.strip()]
    errors = []
    for model in models:
        try:
            return _gemini_one(key, model, system, prompt, search)
        except RetryableError as e:
            if " 429" in str(e)[:12] or "HTTP 429" in str(e):
                errors.append(f"{model}: പരിധി (429)")
                continue
            raise
        except RuntimeError as e:
            if "HTTP 404" in str(e) or "HTTP 400" in str(e):
                errors.append(f"{model}: {str(e)[:60]}")
                continue
            raise
    raise RuntimeError("ഒരു Gemini മോഡലും ലഭ്യമായില്ല: " + "; ".join(errors))


def _gemini_one(key, model, system, prompt, search):
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4},
    }
    if search:
        body["tools"] = [{"google_search": {}}]
    # പുതിയ "AQ." key-കൾ header-ൽ അയച്ചാൽ പ്രവർത്തിക്കില്ല; ?key= ആയി അയക്കുന്നു (പഴയ AIza key-കൾക്കും ഇത് ശരി)
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": key},
        headers={"Content-Type": "application/json"},
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
    model = _env("GROQ_SEARCH_MODEL", "openai/gpt-oss-120b") if search else _env("GROQ_MODEL", "openai/gpt-oss-120b")
    body = {
        "model": model,
        "temperature": 0.4,
        "max_completion_tokens": 6000,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    if search:
        body.update({"tools": [{"type": "browser_search"}], "tool_choice": "required", "reasoning_effort": "low"})
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json=body,
        timeout=240,
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
