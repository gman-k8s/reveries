import io
import json

from reveries import llm


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_urlopen(captured, body):
    def urlopen(request, timeout):
        captured.update(url=request.full_url, timeout=timeout,
                        headers={k.lower(): v for k, v in request.header_items()},
                        payload=json.loads(request.data))
        return FakeResponse(json.dumps(body).encode())
    return urlopen


def test_openai_compatible(monkeypatch):
    captured = {}
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen(
        captured, {"choices": [{"message": {"content": "Kiste 4."}}]}))
    call = llm.openai_compatible("http://vllm:8000/v1/", "qwen", api_key="k", timeout=5)
    assert call("Prompt") == "Kiste 4."
    assert captured["url"] == "http://vllm:8000/v1/chat/completions"
    assert captured["timeout"] == 5
    assert captured["headers"]["authorization"] == "Bearer k"
    assert captured["payload"]["messages"] == [{"role": "user", "content": "Prompt"}]


def test_gemini(monkeypatch):
    captured = {}
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen(captured, {
        "candidates": [{"content": {"parts": [{"text": "intern", "thought": True},
                                              {"text": "Kiste 4."}]}}]}))
    call = llm.gemini("gemini-flash", "secret")
    assert call("Prompt") == "Kiste 4."
    assert captured["url"].endswith("/models/gemini-flash:generateContent")
    assert captured["headers"]["x-goog-api-key"] == "secret"
    assert captured["timeout"] < 60
