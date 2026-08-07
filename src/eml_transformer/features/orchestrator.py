from __future__ import annotations

import logging

import pandas as pd

from eml_transformer.features.registry import (
    FEATURES,
    get_feature_function,
)
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.storage import Storage


logger = logging.getLogger(__name__)


class FeatureOrchestrator:
    def __init__(
        self,
        storage: Storage,
        paths: StoragePaths,
    ) -> None:
        self.storage = storage
        self.paths = paths

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

    def run_all(
        self,
        sources: list[str] | None = None,
    ) -> dict[str, pd.DataFrame]:
        selected_sources = (
            sources
            if sources is not None
            else list(FEATURES)
        )

        results: dict[str, pd.DataFrame] = []

        for source in selected_sources:
            try:
                results.append(self.run_source(source))
            except Exception:
                logger.exception(
                    "Feature construction failed for source=%s",
                    source,
                )

        return results