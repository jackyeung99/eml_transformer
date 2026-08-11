from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pandas as pd

from eml_transformer.features.registry import get_feature_function
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.storage import Storage

logger = logging.getLogger(__name__)


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
        source_name: str,
        source_config: Mapping[str, Any],
    ) -> FeatureResult:

        input_ref: str | None = None
        output_ref: str | None = None
        records_read = 0

        logger.info(
            "Building features | source=%s ",
            source_name,

        )

        try:
            stage_config = source_config.get("features", {})

            if not isinstance(stage_config, Mapping):
                raise TypeError(
                    f"Feature configuration for {source_name!r} "
                    "must be a mapping"
                )

            input_ref = str(
                stage_config.get(
                    "input",
                    f"silver:{source_name}:records",
                )
            )
            output_ref = str(
                stage_config.get(
                    "output",
                    f"gold:{source_name}:features",
                )
            )

            builder_name = str(
                stage_config.get("builder", source_name)
            )
            write_mode = str(
                stage_config.get("write_mode", "replace")
            )

            options = stage_config.get("options", {})

            if not isinstance(options, Mapping):
                raise TypeError(
                    f"Feature options for {source_name!r} "
                    "must be a mapping"
                )

            # This intentionally loads the complete dataset because the
            # builder may require global context for sorting, pivots,
            # rolling windows, or lag construction.
            records = self.storage.read_dataset(input_ref)
            records_read = len(records)

            if records.empty:
                message = f"No feature input found: {input_ref}"

                logger.warning(
                    "%s | source=%s ",
                    message,
                    source_name,
          
                )

                return FeatureResult(
                    status="skipped",
                    source=source_name,
                    records_read=0,
                    records_written=0,
                    input_ref=input_ref,
                    output_ref=output_ref,
                    error=message,
                )

            build_features = get_feature_function(builder_name)

            features = build_features(
                records,
                **dict(options),
            )

            if not isinstance(features, pd.DataFrame):
                raise TypeError(
                    f"Feature builder {builder_name!r} returned "
                    f"{type(features).__name__}, expected DataFrame"
                )

            records_written = self.storage.write_batches(
                ref=output_ref,
                batches=(features,),
                mode=write_mode,
            )

            logger.info(
                "Feature building completed | source=%s | read=%s | written=%s",
                source_name,
                records_read,
                records_written,
            )

            return FeatureResult(
                status="success",
                source=source_name,
                records_read=records_read,
                records_written=records_written,
                input_ref=input_ref,
                output_ref=output_ref,
            )

        except Exception as error:
            logger.exception(
                "Feature building failed | source=%s",
                source_name,
            )

            return FeatureResult(
                status="failed",
                source=source_name,
                records_read=records_read,
                records_written=0,
                input_ref=input_ref,
                output_ref=output_ref,
                error=str(error),
            )