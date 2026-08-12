"""Regression tests for the model-router fallback chain.

Guards the fix that keeps AI chat working on credit-less OpenRouter accounts:
when the primary model fails with a provider-side error (402 no credits /
429 rate-limit / 5xx), the router must move to the next configured model
instead of surfacing ``ModelRouterError``.
"""
from app.ai import model_router
from app.ai.model_router import ModelRouterError


def test_complete_falls_back_on_retryable_error(monkeypatch):
    calls = []

    def fake_one(model, messages, temperature):
        calls.append(model)
        if model == "first":
            raise ModelRouterError("402 no credits", status_code=402)
        return "ok"

    monkeypatch.setattr(model_router, "_complete_one", fake_one)
    monkeypatch.setattr(model_router.settings, "AI_MODEL_FALLBACKS", "second,third")

    result = model_router.complete([{"role": "user", "content": "hi"}], model="first")

    assert result == "ok"
    assert calls == ["first", "second"]


def test_complete_with_tools_falls_back(monkeypatch):
    calls = []

    def fake_one(messages, tools, model, temperature, tool_choice, max_tokens):
        calls.append(model)
        if model == "primary":
            raise ModelRouterError("429 rate limited", status_code=429)
        return {"content": "done", "tool_calls": []}

    monkeypatch.setattr(model_router, "_complete_with_tools_one", fake_one)
    monkeypatch.setattr(model_router.settings, "AI_MODEL_FALLBACKS", "backup")

    result = model_router.complete_with_tools(
        [{"role": "user", "content": "hi"}], tools=[], model="primary"
    )

    assert result["content"] == "done"
    assert calls == ["primary", "backup"]


def test_complete_does_not_retry_config_errors(monkeypatch):
    calls = []

    def fake_one(model, messages, temperature):
        calls.append(model)
        raise ModelRouterError("OPENROUTER_API_KEY is not configured")

    monkeypatch.setattr(model_router, "_complete_one", fake_one)
    monkeypatch.setattr(model_router.settings, "AI_MODEL_FALLBACKS", "backup")

    try:
        model_router.complete([{"role": "user", "content": "hi"}], model="first")
    except ModelRouterError:
        pass
    else:
        raise AssertionError("expected ModelRouterError")

    # A missing-key error (no status_code) must NOT retry other models.
    assert calls == ["first"]


def test_model_chain_dedupes(monkeypatch):
    monkeypatch.setattr(model_router.settings, "AI_MODEL_FALLBACKS", "b, c, a")
    chain = model_router._model_chain("a")
    assert chain == ["a", "b", "c"]


def test_complete_falls_back_on_model_not_found(monkeypatch):
    """An unknown model id (400/404 "model not found") must move to the next
    fallback instead of killing the whole chain."""
    calls = []

    def fake_one(model, messages, temperature):
        calls.append(model)
        if model == "ghost-model":
            raise ModelRouterError("404 model 'ghost-model' not found", status_code=404)
        return "ok"

    monkeypatch.setattr(model_router, "_complete_one", fake_one)
    monkeypatch.setattr(model_router.settings, "AI_MODEL_FALLBACKS", "gemini-2.5-pro")

    result = model_router.complete(
        [{"role": "user", "content": "hi"}], model="ghost-model"
    )

    assert result == "ok"
    assert calls == ["ghost-model", "gemini-2.5-pro"]
