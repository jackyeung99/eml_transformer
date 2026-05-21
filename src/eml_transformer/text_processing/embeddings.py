from __future__ import annotations

from sentence_transformers import SentenceTransformer


class SentenceTransformerEmbedder:
    def __init__(
        self,
        model_name: str,
        device: str | None = None,
        normalize_embeddings: bool = True,
        trust_remote_code: bool = True,
    ):
        self.model_name = model_name
        self.normalize_embeddings = normalize_embeddings

        self.model = SentenceTransformer(
            model_name,
            device=device,
            trust_remote_code=trust_remote_code,
        )

    def embed(
        self,
        texts: list[str],
        batch_size: int = 32,
    ) -> list[list[float]]:
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=True,
        )

        return embeddings.tolist()