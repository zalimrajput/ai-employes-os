"""Text embedding helpers for pgvector storage.

Provider order: OpenAI (``OPENAI_API_KEY``) first, then Google Gemini
(``GOOGLE_AI_KEY``) as a fallback — mirrors the model_router's provider
fallbacks so demo/self-host setups with only a Google key still get real
vector search. When neither key is configured the helpers return ``None`` and
the retriever falls back to keyword matching so RAG keeps working offline.

Google output dimensionality is pinned to ``EMBEDDING_DIMENSION`` (1536) via
``outputDimensionality``, which keeps vectors compatible with the pgvector
columns created for ``text-embedding-3-small`` — no schema change needed.
"""
import logging
import time
from typing import Optional

logger = logging.getLogger("app.ai.embeddings")

# Google's batch API rejects oversized payloads; keep well under the limit.
_GOOGLE_BATCH_SIZE = 50


def embeddings_available() -> bool:
    """True when any configured provider can produce embeddings."""
    from app.core.config import settings

    return bool(settings.OPENAI_API_KEY or settings.GOOGLE_AI_KEY)


def embed(texts: list[str]) -> Optional[list[list[float]]]:
    """Return a list of vectors for the given texts, or None if unsupported."""
    from app.core.config import settings

    texts = [t for t in texts if t is not None and str(t).strip()]
    if not texts:
        return []

    if settings.OPENAI_API_KEY:
        vectors = _embed_openai(texts)
        if vectors is not None:
            return vectors
        logger.warning("openai embeddings failed; falling back to google")
    if settings.GOOGLE_AI_KEY:
        return _embed_google(texts)
    logger.info("no embedding provider configured (OPENAI_API_KEY/GOOGLE_AI_KEY)")
    return None


def _embed_openai(texts: list[str]) -> Optional[list[list[float]]]:
    from app.core.config import settings

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.embeddings.create(
            model=settings.EMBEDDING_MODEL, input=texts
        )
        return [item.embedding for item in resp.data]
    except Exception as exc:  # noqa: BLE001
        logger.warning("openai embedding failure: %s", exc, exc_info=True)
        return None


def _embed_google(texts: list[str]) -> Optional[list[list[float]]]:
    """Embed via Google Gemini's batchEmbedContents REST endpoint."""
    from app.core.config import settings

    model = settings.GOOGLE_EMBEDDING_MODEL
    dim = settings.EMBEDDING_DIMENSION
    # Key via header (not the URL) so it never leaks into request logs.
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:batchEmbedContents"
    )

    def _batch(chunk: list[str]) -> Optional[list[list[float]]]:
        import httpx

        payload = {
            "model": f"models/{model}",
            "requests": [
                {
                    "model": f"models/{model}",
                    "content": {"parts": [{"text": t}]},
                    # Per-request (top-level is rejected by the API).
                    "outputDimensionality": dim,
                }
                for t in chunk
            ],
        }
        headers = {"x-goog-api-key": settings.GOOGLE_AI_KEY}
        # One retry on transient failures (429/5xx) so a hiccup never leaves a
        # freshly uploaded document without embeddings.
        for attempt in range(2):
            try:
                resp = httpx.post(url, json=payload, headers=headers, timeout=60)
            except Exception as exc:  # noqa: BLE001
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                logger.warning("google embedding error: %s", exc, exc_info=True)
                return None
            if resp.status_code < 300:
                data = resp.json()
                return [e["values"] for e in data.get("embeddings", [])]
            if attempt == 0 and resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.0)
                continue
            logger.warning(
                "google embedding failed: %s %s",
                resp.status_code,
                resp.text[:200],
            )
            return None
        return None

    vectors: list[list[float]] = []
    for i in range(0, len(texts), _GOOGLE_BATCH_SIZE):
        batch = _batch(texts[i : i + _GOOGLE_BATCH_SIZE])
        if batch is None:
            return None
        vectors.extend(batch)
    return vectors


def embed_text(text: str) -> Optional[list[float]]:
    result = embed([text])
    return result[0] if result else None
