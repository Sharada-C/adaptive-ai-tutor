from app.core.config import settings
from app.services.ollama_client import post_json


OLLAMA_URL = f"{settings.ollama_base_url.rstrip('/')}/api/embeddings"
EMBEDDING_MODEL = settings.embedding_model


def generate_embedding(text: str) -> list[float]:
    data = post_json(
        OLLAMA_URL,
        {
            "model": EMBEDDING_MODEL,
            "prompt": text,
        },
    )

    embedding = data.get("embedding")

    if not embedding:
        raise RuntimeError("Ollama returned no embedding.")

    if len(embedding) != 768:
        raise RuntimeError(
            f"Expected 768-dimensional embedding, "
            f"got {len(embedding)}."
        )

    return embedding