"""One-off dev utility: embed existing documents/articles lacking vectors.

Documents uploaded before an embedding provider was configured have NULL
embedding columns and were never searchable via vector RAG. This re-embeds:
  - every knowledge_articles row with a NULL embedding (embed its content)
  - every documents row with a NULL embedding (embed its extracted text)

Idempotent; safe to re-run.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.ai.embeddings import embed, embeddings_available
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.knowledge_base import KnowledgeArticle


def main() -> int:
    if not embeddings_available():
        print("No embedding provider configured (OPENAI_API_KEY/GOOGLE_AI_KEY) — nothing to do.")
        return 1

    db: Session = SessionLocal()
    try:
        articles = (
            db.query(KnowledgeArticle)
            .filter(KnowledgeArticle.embedding.is_(None))
            .all()
        )
        docs = (
            db.query(Document)
            .filter(Document.embedding.is_(None))
            .all()
        )
        print(f"articles without embedding: {len(articles)}")
        print(f"documents without embedding: {len(docs)}")

        if articles:
            vectors = embed([a.content or "" for a in articles])
            if vectors is not None:
                for a, v in zip(articles, vectors):
                    a.embedding = v
                db.commit()
                print(f"embedded {len(articles)} articles")
            else:
                print("embedding failed for articles")

        if docs:
            # Doc-level vector: first ~4000 chars. ingest_document uses the
            # first chunk's vector instead; both are valid 1536-dim vectors
            # used only for ranking, so they need not match exactly.
            texts = [(d.extracted_text or "")[:4000] for d in docs]
            vectors = embed(texts)
            if vectors is not None:
                for d, v in zip(docs, vectors):
                    d.embedding = v
                db.commit()
                print(f"embedded {len(docs)} documents")
            else:
                print("embedding failed for documents")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
