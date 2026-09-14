import requests


OLLAMA_URL = "http://127.0.0.1:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"


def generate_embedding(text: str) -> list[float]:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": EMBEDDING_MODEL,
            "prompt": text,
        },
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()

    embedding = data.get("embedding")

    if not embedding:
        raise RuntimeError("Ollama returned no embedding.")

    if len(embedding) != 768:
        raise RuntimeError(
            f"Expected 768-dimensional embedding, "
            f"got {len(embedding)}."
        )

    return embedding