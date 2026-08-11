from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


def _clean(x: str) -> str:
    return (
        str(x)
        .strip()
        .replace(" ", "_")
        .replace("/", "-")
        .replace("\\", "-")
        .replace("=", "-")
    )


def _p(*parts: str) -> str:
    return str(PurePosixPath(*parts))


@dataclass(frozen=True, slots=True)
class DatasetRef:
    layer: str
    source: str
    artifact: str

    @classmethod
    def parse(cls, value: str) -> DatasetRef:
        try:
            layer, source, artifact = value.split(":")
        except ValueError as error:
            raise ValueError(
                f"Invalid dataset reference {value!r}. "
                "Expected 'layer:source:artifact'."
            ) from error

        if layer not in {"bronze", "silver", "gold"}:
            raise ValueError(f"Unknown layer: {layer!r}")

        return cls(layer, source, artifact)
    


@dataclass(frozen=True, slots=True)
class StoragePaths:
    root: str = "data"

    def dataset(
        self,
        ref: DatasetRef | str,
    ) -> str:
        if isinstance(ref, str):
            ref = DatasetRef.parse(ref)

        if ref.layer == "gold":
            if ref.artifact == "dataset":
                return _p(
                    self.root,
                    "gold",
                    "datasets",
                    f"name={_clean(ref.source)}",
                )

            return _p(
                self.root,
                "gold",
                _clean(ref.artifact),
                f"source={_clean(ref.source)}",
            )

        return _p(
            self.root,
            ref.layer,
            f"source={_clean(ref.source)}",
            f"artifact={_clean(ref.artifact)}",
        )

    def part(
        self,
        ref: DatasetRef | str,
        number: int,
        extension: str = "parquet",
    ) -> str:
        return _p(
            self.dataset(ref),
            f"part-{number:05d}.{extension}",
        )

    def bronze_records(
        self,
        source: str,
    ) -> str:
        return _p(
            self.root,
            "bronze",
            f"source={_clean(source)}",
            # f"ingest_date={ingest_date}",
            "records.jsonl",
        )

    def dedupe_state(self, source: str) -> str:
        return _p(
            self.root,
            "metadata",
            "dedupe",
            f"source={_clean(source)}.json",
        )

    def checkpoint(self, source: str) -> str:
        return _p(
            self.root,
            "metadata",
            "checkpoints",
            f"source={_clean(source)}.json",
        )