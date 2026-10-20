"""Optionale LLM-Adapter, nur Standardbibliothek (urllib).

Jeder Adapter liefert eine Callable str -> str für apply(llm=...). Fehler werden
als Exception geworfen; apply() fängt sie ab und fällt auf Vorlage/Original zurück.
"""

import json
import urllib.request

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _post_json(url, payload, headers, timeout):
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def openai_compatible(base_url, model, api_key=None, timeout=20, max_tokens=150,
                      temperature=0.9):
    """Chat-Completions-API, z. B. lokaler vLLM-Server (base_url = „http://host:8000/v1“)."""
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def call(prompt):
        data = _post_json(url, {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }, headers, timeout)
        return data["choices"][0]["message"]["content"]

    return call


def gemini(model, api_key, timeout=20, max_tokens=400, temperature=0.9):
    """Google-Gemini-API (generateContent).

    max_tokens großzügiger als bei openai_compatible, weil „denkende“ Modelle
    einen Teil davon intern verbrauchen.
    """
    url = GEMINI_URL.format(model=model)
    headers = {"x-goog-api-key": api_key}

    def call(prompt):
        data = _post_json(url, {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        }, headers, timeout)
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))

    return call
