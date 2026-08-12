"""Embedding provider unit tests (no real network calls)."""
import sys

sys.path.insert(0, ".")

import app.ai.embeddings as emb
from app.core.config import settings


def _keys(monkeypatch, openai=None, google=None):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", openai)
    monkeypatch.setattr(settings, "GOOGLE_AI_KEY", google)


def test_embeddings_available_false_without_keys(monkeypatch):
    _keys(monkeypatch)
    assert emb.embeddings_available() is False


def test_embeddings_available_with_either_key(monkeypatch):
    _keys(monkeypatch, google="g")
    assert emb.embeddings_available() is True
    _keys(monkeypatch, openai="o")
    assert emb.embeddings_available() is True


def test_embed_returns_none_without_provider(monkeypatch):
    _keys(monkeypatch)
    assert emb.embed(["hi"]) is None


def test_embed_uses_openai_first(monkeypatch):
    _keys(monkeypatch, openai="o", google="g")
    seen = {}

    def fake_openai(texts):
        seen["openai"] = texts
        return [[1.0]]

    def fail_google(texts):
        raise AssertionError("google must not run when an openai key is present")

    monkeypatch.setattr(emb, "_embed_openai", fake_openai)
    monkeypatch.setattr(emb, "_embed_google", fail_google)
    assert emb.embed(["hello"]) == [[1.0]]
    assert seen["openai"] == ["hello"]


def _raise_openai(texts):
    raise AssertionError("openai not configured")


def test_embed_falls_back_to_google(monkeypatch):
    _keys(monkeypatch, openai=None, google="g")
    seen = {}

    def fake_google(texts):
        seen["google"] = texts
        return [[0.0, 1.0]]

    monkeypatch.setattr(emb, "_embed_openai", _raise_openai)
    monkeypatch.setattr(emb, "_embed_google", fake_google)
    assert emb.embed(["hi"]) == [[0.0, 1.0]]
    assert seen["google"] == ["hi"]


def test_embed_uses_google_when_openai_fails(monkeypatch):
    """A configured-but-failing OpenAI provider must not block embeddings:
    embed() falls through to Google instead of returning None."""
    _keys(monkeypatch, openai="broken", google="g")
    seen = {}
    monkeypatch.setattr(emb, "_embed_openai", lambda texts: None)

    def fake_google(texts):
        seen["google"] = texts
        return [[1.0, 2.0]]

    monkeypatch.setattr(emb, "_embed_google", fake_google)
    assert emb.embed(["hi"]) == [[1.0, 2.0]]
    assert seen["google"] == ["hi"]


def test_embed_returns_none_when_all_providers_fail(monkeypatch):
    _keys(monkeypatch, openai="broken", google="g")
    monkeypatch.setattr(emb, "_embed_openai", lambda texts: None)
    monkeypatch.setattr(emb, "_embed_google", lambda texts: None)
    assert emb.embed(["hi"]) is None


def test_embed_filters_blank_texts(monkeypatch):
    _keys(monkeypatch, google="g")
    seen = {}
    monkeypatch.setattr(emb, "_embed_google", lambda texts: seen.update(texts=texts) or [])
    emb.embed(["  ", None, "x"])
    assert seen["texts"] == ["x"]


def test_google_http_payload(monkeypatch):
    _keys(monkeypatch, google="secret")
    calls = {}

    def fake_post(url, json=None, headers=None, timeout=30):
        calls["url"] = url
        calls["json"] = json
        calls["headers"] = headers

        class Resp:
            status_code = 200

            def json(self):
                return {
                    "embeddings": [
                        {"values": [0.1] * 1536},
                        {"values": [0.2] * 1536},
                    ]
                }

        return Resp()

    monkeypatch.setattr("httpx.post", fake_post)
    result = emb._embed_google(["a", "b"])
    assert len(result) == 2
    assert len(result[0]) == 1536
    assert "batchEmbedContents" in calls["url"]
    # key travels in the header, not the URL
    assert calls["headers"]["x-goog-api-key"] == "secret"
    assert "?key=" not in calls["url"]
    assert calls["json"]["requests"][0]["outputDimensionality"] == 1536
    assert calls["json"]["requests"][1]["content"]["parts"][0]["text"] == "b"


def test_google_batches_large_inputs(monkeypatch):
    _keys(monkeypatch, google="secret")
    calls = []

    def fake_post(url, json=None, headers=None, timeout=30):
        calls.append(json["requests"])

        class Resp:
            status_code = 200

            def json(self):
                return {"embeddings": [{"values": [1.0]} for _ in json["requests"]]}

        return Resp()

    monkeypatch.setattr("httpx.post", fake_post)
    texts = ["t%d" % i for i in range(emb._GOOGLE_BATCH_SIZE + 1)]
    result = emb._embed_google(texts)
    assert len(result) == 51
    assert len(calls) == 2


def test_google_retries_on_429(monkeypatch):
    _keys(monkeypatch, google="secret")
    calls = []

    def fake_post(url, json=None, headers=None, timeout=30):
        calls.append(1)

        class Resp:
            status_code = 429 if len(calls) == 1 else 200

            def json(self):
                return {"embeddings": [{"values": [1.0]}]}

        return Resp()

    monkeypatch.setattr("httpx.post", fake_post)
    result = emb._embed_google(["x"])
    assert result == [[1.0]]
    assert len(calls) == 2


def test_retriever_vector_ok_reflects_provider(monkeypatch):
    from app.ai import retriever

    _keys(monkeypatch)
    assert retriever._vector_ok() is False
    _keys(monkeypatch, google="g")
    assert retriever._vector_ok() is True
    _keys(monkeypatch, openai="o")
    assert retriever._vector_ok() is True


def test_keyword_score_phrases_outrank_words():
    from app.ai.retriever import _keyword_score

    assert _keyword_score("vacation policy", "Our vacation policy allows 20 days") >= 3
    assert _keyword_score("policies", "unrelated text") == 0
    assert _keyword_score("terms", "terms of service") >= 1


def test_vector_param_format():
    from app.ai.retriever import _vector_param

    assert _vector_param([0.1, 0.2]) == "[0.1,0.2]"
