from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd
from sentence_transformers import SentenceTransformer

from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.storage import Storage

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    status: str

    model_name: str

    records_read: int
    embeddings_created: int
    embeddings_skipped: int
    records_failed: int = 0

    output_key: str | None = None

    error: str | None = None

    records: pd.DataFrame | None = None


class EmbeddingPipeline:
    def __init__(
        self,
        storage: Storage,
        paths: StoragePaths,
    ):
        self.storage = storage
        self.paths = paths

    def run(
        self,
        embedding_config: dict[str, Any],
        source_configs: dict[str, dict[str, Any]],
    ) -> EmbeddingResult:
        


        model_name = embedding_config.get(
            "model",
            "sentence-transformers/all-MiniLM-L6-v2",
        )

        text_columns = embedding_config.get(
            "text_columns",
            ["title", "text"],
        )

        batch_size = embedding_config.get(
            "batch_size",
            32,
        )

        normalize_embeddings = embedding_config.get(
            "normalize_embeddings",
            True,
        )

        output_key = self.paths.gold_records(
            model_name=model_name,
        )

        sources = list(source_configs.keys())

        logger.info(
            "Starting embedding pipeline | model=%s | sources=%s | batch_size=%s | normalize=%s",
            model_name,
            sources,
            batch_size,
            normalize_embeddings,
        )

        try:
            df = self._load_records(sources)

            records_read = len(df)

            logger.info(
                "Loaded standardized records | records=%s | sources=%s",
                records_read,
                len(sources),
            )

            if df.empty:
                logger.warning(
                    "No standardized records found | sources=%s",
                    sources,
                )

                return EmbeddingResult(
                    status="empty",
                    model_name=model_name,
                    records_read=0,
                    embeddings_created=0,
                    embeddings_skipped=0,
                    output_key=output_key,
                    records=df,
                )


            df["embedding_text"] = df.apply(
                lambda row: self._build_embedding_text(
                    row=row.to_dict(),
                    text_columns=text_columns,
                ),
                axis=1,
            )

            valid_mask = (
                df["embedding_text"]
                .fillna("")
                .str.strip()
                .ne("")
            )

            valid_df = df.loc[valid_mask].copy()

            embeddings_skipped = len(df) - len(valid_df)

    

            if valid_df.empty:
                logger.warning(
                    "No valid text available for embedding | records=%s",
                    records_read,
                )

                return EmbeddingResult(
                    status="no_valid_text",
                    model_name=model_name,
                    records_read=records_read,
                    embeddings_created=0,
                    embeddings_skipped=embeddings_skipped,
                    output_key=output_key,
                    records=df,
                )

            logger.info(
                "Loading embedding model | model=%s",
                model_name,
            )

            model = self._load_model(model_name)

            logger.info(
                "Encoding records | records=%s | batch_size=%s",
                len(valid_df),
                batch_size,
            )

            embeddings = model.encode(
                valid_df["embedding_text"].tolist(),
                batch_size=batch_size,
                show_progress_bar=True,
                convert_to_numpy=True,
                normalize_embeddings=normalize_embeddings,
            )

            valid_df["embedding"] = embeddings.tolist()
            valid_df["embedding_model"] = model_name

            logger.info(
                "Writing embeddings | output_key=%s | rows=%s",
                output_key,
                len(valid_df),
            )

            self.storage.write_csv(
                valid_df,
                output_key,
            )

            logger.info(
                "Embedding pipeline complete | status=success | created=%s | skipped=%s | output_key=%s",
                len(valid_df),
                embeddings_skipped,
                output_key,
            )

            return EmbeddingResult(
                status="success",
                model_name=model_name,
                records_read=records_read,
                embeddings_created=len(valid_df),
                embeddings_skipped=embeddings_skipped,
                output_key=output_key,
                records=valid_df,
            )

        except Exception as exc:
            logger.exception(
                "Embedding pipeline failed | model=%s | output_key=%s",
                model_name,
                output_key,
            )

            return EmbeddingResult(
                status="failed",
                model_name=model_name,
                records_read=0,
                embeddings_created=0,
                embeddings_skipped=0,
                output_key=output_key,
                error=str(exc),
            )

    def _load_model(
        self,
        model_name: str,
    ) -> SentenceTransformer:
        return SentenceTransformer(model_name)

    def _load_records(
        self,
        sources: list[str],
    ) -> pd.DataFrame:
        dfs = []

        logger.info(
            "Loading silver records | sources=%s",
            sources,
        )

        for source in sources:
            key = self.paths.silver_records(source)

            df = self.storage.read_csv(key)

            if df.empty:
                logger.warning(
                    "No silver records found | source=%s | key=%s",
                    source,
                    key,
                )
                continue

            logger.info(
                "Loaded source records | source=%s | rows=%s",
                source,
                len(df),
            )

            dfs.append(df)

        if not dfs:
            logger.warning(
                "No silver records loaded from any source"
            )
            return pd.DataFrame()

        merged = pd.concat(
            dfs,
            ignore_index=True,
        )

        before_dedupe = len(merged)

        merged = merged.drop_duplicates(
            subset=["record_id"],
        ).sort_values(by=['published_at'])


        after_dedupe = len(merged)

        logger.info(
            "Merged silver records | before_dedupe=%s | after_dedupe=%s | duplicates_removed=%s",
            before_dedupe,
            after_dedupe,
            before_dedupe - after_dedupe,
        )

        return merged

    def _build_embedding_text(
        self,
        row: dict[str, Any],
        text_columns: list[str],
    ) -> str:
        parts = []

        for column in text_columns:
            value = row.get(column)

            if value is None:
                continue

            value = str(value).strip()

            if value:
                parts.append(value)

        return "\n\n".join(parts)