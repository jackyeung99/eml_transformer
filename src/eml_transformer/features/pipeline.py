from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pandas as pd

from eml_transformer.features.registry import get_feature_function
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.base import Storage
from eml_transformer.config.loader import FeatureDefinition

from eml_transformer.logging import get_logger

logger = get_logger(__name__)

@dataclass(slots=True)
class FeatureResult:
    status: str
    source: str
    records_read: int
    records_written: int
    input_ref: str | None = None
    output_ref: str | None = None
    error: str | None = None

    def to_summary(self) -> dict[str, object]:
        summary: dict[str, object] = {
            "source": self.source,
            "status": self.status,
            "read": self.records_read,
            "written": self.records_written,
        }

        if self.input_ref is not None:
            summary["input"] = self.input_ref

        if self.output_ref is not None:
            summary["output"] = self.output_ref

        if self.error is not None:
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


    def build_feature_set(
        self,
        definition: FeatureDefinition,
    ) -> FeatureResult:
        input_ref = definition.input
        output_ref = definition.output
        records_read = 0

        logger.info(
            "Building feature set | feature=%s | builder=%s | input=%s",
            definition.name,
            definition.builder,
            input_ref,
        )

        try:
            if not definition.enabled:
                return FeatureResult(
                    status="skipped",
                    source=definition.name,
                    records_read=0,
                    records_written=0,
                    input_ref=input_ref,
                    output_ref=output_ref,
                    error="Feature set is disabled",
                )

            write_mode = str(
                definition.settings.get("write_mode", "replace")
            )
            options = definition.settings.get("options", {})

            if not isinstance(options, Mapping):
                raise TypeError(
                    f"Options for feature set {definition.name!r} "
                    "must be a mapping"
                )

            records = self.storage.read_dataset(input_ref)

            if not isinstance(records, pd.DataFrame):
                raise TypeError(
                    f"Input {input_ref!r} returned "
                    f"{type(records).__name__}, expected DataFrame"
                )

            records_read = len(records)

            if records.empty:
                message = f"No feature input found: {input_ref}"

                logger.warning(
                    "%s | feature=%s",
                    message,
                    definition.name,
                )

                return FeatureResult(
                    status="skipped",
                    source=definition.name,
                    records_read=0,
                    records_written=0,
                    input_ref=input_ref,
                    output_ref=output_ref,
                    error=message,
                )

            build_features = get_feature_function(
                definition.builder
            )

            features = build_features(
                records,
                **dict(options),
            )

            if not isinstance(features, pd.DataFrame):
                raise TypeError(
                    f"Feature builder {definition.builder!r} returned "
                    f"{type(features).__name__}, expected DataFrame"
                )

            if features.empty:
                return FeatureResult(
                    status="empty",
                    source=definition.name,
                    records_read=records_read,
                    records_written=0,
                    input_ref=input_ref,
                    output_ref=output_ref,
                )


            records_written = self.storage.write_dataframe(
                ref = definition.output,
                frame=features,
            )

            logger.info(
                "Feature building completed | feature=%s "
                "| read=%s | written=%s",
                definition.name,
                records_read,
                records_written,
            )

            return FeatureResult(
                status="success",
                source=definition.name,
                records_read=records_read,
                records_written=records_written,
                input_ref=input_ref,
                output_ref=output_ref,
            )

        except Exception as error:
            logger.exception(
                "Feature building failed | feature=%s",
                definition.name,
            )

            return FeatureResult(
                status="failed",
                source=definition.name,
                records_read=records_read,
                records_written=0,
                input_ref=input_ref,
                output_ref=output_ref,
                error=str(error),
            )