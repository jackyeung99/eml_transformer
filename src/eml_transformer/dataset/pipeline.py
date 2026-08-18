from __future__ import annotations


from dataclasses import dataclass

from eml_transformer.config.loader import DatasetDefinition
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.base import Storage

from eml_transformer.dataset.registry import get_dataset_function

from eml_transformer.logging import get_logger

logger = get_logger(__name__)

@dataclass(slots=True)
class DatasetResult:
    status: str
    name: str
    records_read: int = 0
    records_written: int = 0
    input_refs: tuple[str, ...] = ()
    output_ref: str | None = None
    error: str | None = None

    def to_summary(self) -> dict[str, object]:
        summary: dict[str, object] = {
            "dataset": self.name,
            "status": self.status,
            "read": self.records_read,
            "written": self.records_written,
        }

        if self.input_refs:
            summary["inputs"] = ", ".join(self.input_refs)

        if self.output_ref is not None:
            summary["output"] = self.output_ref

        if self.error is not None:
            summary["error"] = self.error

        return summary


class DatasetOrchestrator:
    def __init__(
        self,
        storage: Storage,
        paths: StoragePaths,
    ) -> None:
        self.storage = storage
        self.paths = paths

    def build_dataset(
        self,
        definition: DatasetDefinition,
    ) -> DatasetResult:
        try:
            logger.info(
                "Building dataset name=%s inputs=%s output=%s builder=%s",
                definition.name,
                definition.inputs,
                definition.output,
                definition.builder,
            )

            inputs = {
                name: self.storage.read_dataset(ref)
                for name, ref in definition.inputs.items()
            } # dict of feature inputs

            builder = get_dataset_function(definition.builder)

            output = builder(
                inputs,
                **definition.settings,
            )

            self.storage.write_dataframe(
                ref=definition.output,
                frame=output,
            )

            return DatasetResult(
                status="success",
                name=definition.name,
                records_read=sum(len(frame) for frame in inputs.values()),
                records_written=len(output),
                input_refs=tuple(definition.inputs.values()),
                output_ref=definition.output,
            )

        except Exception as exc:
            logger.exception(
                "Failed to build dataset name=%s",
                definition.name,
            )

            return DatasetResult(
                status="failed",
                name=definition.name,
                input_refs=tuple(definition.inputs.values()),
                output_ref=definition.output,
                error=str(exc),
            )