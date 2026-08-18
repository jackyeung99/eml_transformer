from __future__ import annotations


from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pandas as pd

from eml_transformer.embeddings.encoder import SentenceTransformerEmbedder
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.base import Storage
from eml_transformer.logging import get_logger

logger = get_logger(__name__)

@dataclass(slots=True)
class EmbeddingResult:
    status: str
    source: str
    model_name: str

    records_read: int
    embeddings_created: int
    embeddings_skipped: int
    records_failed: int = 0

    input_key: str | None = None
    output_key: str | None = None
    error: str | None = None

    def to_summary(self) -> dict[str, object]:
        return {
            "source": self.source,
            "status": self.status,
            "read": self.records_read,
            "embedded": self.embeddings_created,
            "skipped": self.embeddings_skipped,
            "failed": self.records_failed,
            "model": self.model_name,
            "input": self.input_key,
            "output": self.output_key,
            "error": self.error,
        }


# Eventually rename to EmbeddingOrchestrator
class EmbeddingPipeline:
    def __init__(
        self,
        storage: Storage,
        paths: StoragePaths,
        embedder: SentenceTransformerEmbedder | None = None,
    ) -> None:
        self.storage = storage
        self.paths = paths
        self.embedder = embedder

    def run_source(
        self,
        source_name: str,
        embedding_config: dict[str, Any],
    ) -> EmbeddingResult:
        model_name = str(
            embedding_config.get(
                "model",
                "nvidia/llama-nemotron-embed-vl-1b-v2",
            )
        )
        input_type = str(
            embedding_config.get("input_type", "passage")
        )
        embedding_batch_size = int(
            embedding_config.get("embedding_batch_size", 32)
        )
        text_columns = list(
            embedding_config.get("text_columns", ["title", "text"])
        )
        write_mode = str(
            embedding_config.get("write_mode", "append")
        )
        device = embedding_config.get("device")

        input_ref = str(
            embedding_config.get(
                "input",
                f"silver:{source_name}:records",
            )
        )
        output_ref = str(
            embedding_config.get(
                "output",
                f"gold:{source_name}:embeddings",
            )
        )

        input_key = self.paths.dataset(input_ref)
        output_key = self.paths.dataset(output_ref)

        counters = {
            "read": 0,
            "created": 0,
            "skipped": 0,
            "failed": 0,
        }

        try:
            if not self.storage.exists(input_key):
                return EmbeddingResult(
                    status="skipped",
                    source=source_name,
                    model_name=model_name,
                    records_read=0,
                    embeddings_created=0,
                    embeddings_skipped=0,
                    records_failed=0,
                    input_key=input_key,
                    output_key=output_key,
                    error=f"No embedding input found: {input_key}",
                )

            existing_record_ids = (
                self._load_existing_record_ids(output_ref)
                if write_mode == "append"
                else set()
            )

            client = self.embedder or SentenceTransformerEmbedder(
                model_name=model_name,
                device=device,
            )

            output_batches = self._iter_embedding_batches(
                source=source_name,
                input_ref=input_ref,
                client=client,
                model_name=model_name,
                input_type=input_type,
                text_columns=text_columns,
                embedding_batch_size=embedding_batch_size,
                existing_record_ids=existing_record_ids,
                counters=counters,
            )

            self.storage.write_batches(
                ref=output_ref,
                batches=output_batches,
                mode=write_mode,
            )

            if counters["read"] == 0:
                status = "empty"
            elif counters["created"] == 0:
                status = "up_to_date"
            else:
                status = "success"

            return EmbeddingResult(
                status=status,
                source=source_name,
                model_name=model_name,
                records_read=counters["read"],
                embeddings_created=counters["created"],
                embeddings_skipped=counters["skipped"],
                records_failed=counters["failed"],
                input_key=input_key,
                output_key=output_key,
            )

        except Exception as exc:
            logger.exception(
                "Embedding pipeline failed | source=%s",
                source_name,
            )

            return EmbeddingResult(
                status="failed",
                source=source_name,
                model_name=model_name,
                records_read=counters["read"],
                embeddings_created=counters["created"],
                embeddings_skipped=counters["skipped"],
                records_failed=counters["failed"],
                input_key=input_key,
                output_key=output_key,
                error=str(exc),
            )
        
    def _iter_embedding_batches(
        self,
        *,
        source: str,
        input_ref: str,
        client: SentenceTransformerEmbedder,
        model_name: str,
        input_type: str,
        text_columns: list[str],
        embedding_batch_size: int,
        existing_record_ids: set[str],
        counters: dict[str, int],
    ) -> Iterator[pd.DataFrame]:
        for frame in self.storage.read_batches(input_ref):
            counters["read"] += len(frame)

            try:
                output = self._embed_frame(
                    frame=frame,
                    source=source,
                    client=client,
                    model_name=model_name,
                    input_type=input_type,
                    text_columns=text_columns,
                    embedding_batch_size=embedding_batch_size,
                    existing_record_ids=existing_record_ids,
                    counters=counters,
                )
            except Exception:
                counters["failed"] += len(frame)
                logger.exception(
                    "Failed to embed batch | source=%s | rows=%s",
                    source,
                    len(frame),
                )
                continue

            if not output.empty:
                yield output

    def _embed_frame(
        self,
        *,
        frame: pd.DataFrame,
        source: str,
        client: SentenceTransformerEmbedder,
        model_name: str,
        input_type: str,
        text_columns: list[str],
        embedding_batch_size: int,
        existing_record_ids: set[str],
        counters: dict[str, int],
    ) -> pd.DataFrame:
        if frame.empty:
            return frame

        if "record_id" not in frame.columns:
            raise ValueError("Embedding input is missing the 'record_id' column")

        frame = frame.drop_duplicates(
            subset=["record_id"],
            keep="last",
        ).copy()

        frame["embedding_text"] = frame.apply(
            lambda row: self._build_embedding_text(
                row=row.to_dict(),
                text_columns=text_columns,
            ),
            axis=1,
        )

        valid_text = frame["embedding_text"].str.strip().ne("")
        already_embedded = frame["record_id"].isin(existing_record_ids)
        selected = valid_text & ~already_embedded

        counters["skipped"] += int((~selected).sum())

        output = frame.loc[selected].copy()

        if output.empty:
            return output

        embeddings = client.embed(
            output["embedding_text"].tolist(),
            batch_size=embedding_batch_size,
        )

        output["embedding"] = list(embeddings)
        output["embedding_model"] = model_name
        output["embedding_input_type"] = input_type
        output["source"] = source

        created_ids = output["record_id"].astype(str)
        existing_record_ids.update(created_ids)
        counters["created"] += len(output)

        logger.info(
            "Generated embedding batch | source=%s | rows=%s",
            source,
            len(output),
        )

        return output.reset_index(drop=True)

    def _load_existing_record_ids(
        self,
        output_ref: str,
    ) -> set[str]:
        record_ids: set[str] = set()

        for frame in self.storage.read_batches(output_ref):
            if "record_id" in frame.columns:
                record_ids.update(
                    frame["record_id"].dropna().astype(str)
                )

        return record_ids

    @staticmethod
    def _build_embedding_text(
        row: dict[str, Any],
        text_columns: list[str],
    ) -> str:
        parts: list[str] = []

        for column in text_columns:
            value = row.get(column)

            if value is None or pd.isna(value):
                continue

            normalized = str(value).strip()

            if normalized:
                parts.append(normalized)

        return "\n\n".join(parts)