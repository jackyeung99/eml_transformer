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
    datasets_root: str = "data"
    artifacts_root: str = "artifacts"

    # =====================
    # Datasets
    # =====================

    def dataset(
        self,
        ref: DatasetRef | str,
    ) -> str:
        if isinstance(ref, str):
            ref = DatasetRef.parse(ref)

        if ref.layer == "gold":
            return _p(
                self.datasets_root,
                "gold",
                ref.artifact,
                f"dataset={_clean(ref.source)}",
            )

        return _p(
            self.datasets_root,
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
            self.datasets_root,
            "bronze",
            f"source={_clean(source)}",
            "records.jsonl",
        )

    # =====================
    # Metadata
    # =====================

    def dedupe_state(
        self,
        source: str,
    ) -> str:
        return _p(
            self.datasets_root,
            "metadata",
            "dedupe",
            f"source={_clean(source)}.json",
        )

    def checkpoint_key(
        self,
        source: str,
    ) -> str:
        return _p(
            self.datasets_root,
            "metadata",
            "checkpoints",
            f"source={_clean(source)}.json",
        )

    # =====================
    # Models
    # =====================

    def model(
        self,
        name: str,
    ) -> str:
        return _p(
            self.artifacts_root,
            "models",
            f"model={_clean(name)}",
        )

    def model_file(
        self,
        name: str,
    ) -> str:
        return _p(
            self.model(name),
            "model.joblib",
        )

    def model_metadata(
        self,
        name: str,
    ) -> str:
        return _p(
            self.model(name),
            "metadata.json",
        )

    def model_versions(
        self,
        name: str,
    ) -> str:
        return _p(
            self.model(name),
            "versions",
        )

    def model_version(
        self,
        name: str,
        version: str,
    ) -> str:
        return _p(
            self.model_versions(name),
            _clean(version),
        )

    def model_version_file(
        self,
        name: str,
        version: str,
    ) -> str:
        return _p(
            self.model_version(
                name,
                version,
            ),
            "model.joblib",
        )

    def model_version_metadata(
        self,
        name: str,
        version: str,
    ) -> str:
        return _p(
            self.model_version(
                name,
                version,
            ),
            "metadata.json",
        )

    # =====================
    # Experiments
    # =====================

    def experiment(
        self,
        name: str,
    ) -> str:
        return _p(
            self.artifacts_root,
            "experiments",
            f"experiment={_clean(name)}",
        )