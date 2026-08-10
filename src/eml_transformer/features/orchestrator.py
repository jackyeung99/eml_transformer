from __future__ import annotations

import logging

import pandas as pd

from collections.abc import Callable, Mapping
from dataclasses import dataclass, asdict

from eml_transformer.features.registry import (

    get_feature_function,
)
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.storage import Storage


logger = logging.getLogger(__name__)


@dataclass
class FeatureResult:
    status: str
    source: str
    run_id: str
    records_fetched: int
    records_written: int
    records_skipped: int = 0
    bronze_key: str | None = None
    dedupe_key: str | None = None
    error: str | None = None

    def to_summary(self) -> dict[str, object]:
        summary: dict[str, object] = {
            "source": self.source,
            "status": self.status,
            "run_id": self.run_id,
            "fetched": self.records_fetched,
            "written": self.records_written,
            "skipped": self.records_skipped,
        }

        if self.error:
            summary["error"] = self.error

        return summary

    
class FeatureOrchestrator:
    def __init__(
        self,
        storage: Storage,
        paths: StoragePaths,
    ) -> None:
        self.storage = storage
        self.paths = paths

    def run_all(
        self,
        source_configs: Mapping[str, Mapping[str, Any]],
    ) -> list[FeatureResult]:
        """
        Run ingestion once for every configured source.

        Failures are isolated because run_source returns a failed result rather
        than raising an exception.
        """
        return [
            self.run_source(
                source_name=source_name,
                source_config=source_config,
            )
            for source_name, source_config in source_configs.items()
        ]
    
    
    def run_source(
        self,
        source: str,
    ) -> pd.DataFrame:
        logger.info("Building features for source=%s", source)

        records = self.storage.read_parquet(
            self.paths.silver_records(source)
        )

        build_features = get_feature_function(source)
        features = build_features(records)

        self.storage.write_parquet(
            features,
            self.paths.gold_features(source),
        )

        logger.info(
            "Built %s feature rows for source=%s",
            len(features),
            source,
        )

        return features
