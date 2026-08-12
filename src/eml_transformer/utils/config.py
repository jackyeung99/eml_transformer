from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


Config = dict[str, Any]

SOURCE_STAGES = frozenset(
    {
        "ingest",
        "backfill",
        "standardize",
        "scrape",
        "embed",
    }
)


@dataclass(frozen=True, slots=True)
class StorageConfig:
    backend: str = "local"
    root: str = "."

    bucket: str | None = None
    prefix: str = ""
    region: str | None = None

@dataclass(frozen=True, slots=True)
class SourceDefinition:
    name: str
    enabled: bool
    stages: frozenset[str]
    settings: Config


@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    name: str
    enabled: bool
    builder: str
    input: str # one silver input 
    output: str
    settings: Config = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class DatasetDefinition:
    name: str
    enabled: bool
    builder: str
    inputs: str
    output: str
    settings: Config = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class AppConfig:
    storage: StorageConfig
    sources: dict[str, SourceDefinition]
    embeddings: Config
    features: dict[str, FeatureDefinition]
    datasets: dict[str, DatasetDefinition]


def load_yaml(path: str | Path) -> Config:
    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Configuration file does not exist: {path}"
        )

    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    if not isinstance(data, dict):
        raise TypeError(
            f"Configuration must contain a mapping: {path}"
        )

    return data


def resolve_api_keys(
    value: Any,
    *,
    source_name: str,
) -> Any:
    if isinstance(value, dict):
        resolved = {
            key: resolve_api_keys(
                item,
                source_name=source_name,
            )
            for key, item in value.items()
            if key != "api_key_env"
        }

        api_key_env = value.get("api_key_env")

        if api_key_env is not None:
            if not isinstance(api_key_env, str) or not api_key_env:
                raise ValueError(
                    f"Source {source_name!r} has an invalid "
                    "'api_key_env'"
                )

            api_key = os.getenv(api_key_env)

            if not api_key:
                raise EnvironmentError(
                    f"Source {source_name!r} requires environment "
                    f"variable {api_key_env!r}"
                )

            resolved["api_key"] = api_key

        return resolved

    if isinstance(value, list):
        return [
            resolve_api_keys(
                item,
                source_name=source_name,
            )
            for item in value
        ]

    return value


def build_source_definition(
    *,
    name: str,
    entry: Any,
    config_dir: Path,
) -> SourceDefinition:
    if not isinstance(entry, dict):
        raise TypeError(
            f"Source {name!r} must be a mapping"
        )

    config_file = entry.get("config")

    if not isinstance(config_file, str) or not config_file:
        raise ValueError(
            f"Source {name!r} must define a config file"
        )

    source_config_path = (
        config_dir / config_file
    ).resolve()

    settings = load_yaml(source_config_path)
    settings = resolve_api_keys(
        settings,
        source_name=name,
    )

    raw_stages = entry.get("stages", [])

    if not isinstance(raw_stages, list):
        raise TypeError(
            f"Stages for source {name!r} must be a list"
        )

    if not all(isinstance(stage, str) for stage in raw_stages):
        raise TypeError(
            f"Every stage for source {name!r} must be a string"
        )

    stages = frozenset(raw_stages)
    unknown_stages = stages - SOURCE_STAGES

    if unknown_stages:
        unknown = ", ".join(sorted(unknown_stages))
        valid = ", ".join(sorted(SOURCE_STAGES))

        raise ValueError(
            f"Source {name!r} contains unknown stages: {unknown}. "
            f"Valid stages: {valid}"
        )

    enabled = entry.get("enabled", True)

    if not isinstance(enabled, bool):
        raise TypeError(
            f"'enabled' for source {name!r} must be a boolean"
        )

    return SourceDefinition(
        name=name,
        enabled=enabled,
        stages=stages,
        settings=settings,
    )

def build_source_definitions(
    cfg: Config,
    *,
    config_dir: Path,
) -> dict[str, SourceDefinition]:
    sources_cfg = cfg.get("sources", {})

    if not isinstance(sources_cfg, dict):
        raise TypeError("'sources' must be a mapping")

    return {
        name: build_source_definition(
            name=name,
            entry=entry,
            config_dir=config_dir,
        )
        for name, entry in sources_cfg.items()
    }

def build_feature_definition(
    *,
    name: str,
    entry: Any,
) -> FeatureDefinition:
    if not isinstance(entry, dict):
        raise TypeError(
            f"Feature {name!r} must be a mapping"
        )

    builder = entry.get("builder")

    if not isinstance(builder, str) or not builder:
        raise ValueError(
            f"Feature {name!r} must define a builder"
        )

    raw_inputs = entry.get("input",)

    if not isinstance(raw_inputs, str):
        raise TypeError(
            f"Inputs for feature {name!r} must be a string"
        )

    output = entry.get("output")

    if not isinstance(output, str) or not output:
        raise ValueError(
            f"Feature {name!r} must define an output"
        )

    enabled = entry.get("enabled", True)

    if not isinstance(enabled, bool):
        raise TypeError(
            f"'enabled' for feature {name!r} must be a boolean"
        )

    settings = entry.get("settings", {})

    if not isinstance(settings, dict):
        raise TypeError(
            f"Settings for feature {name!r} must be a mapping"
        )

    return FeatureDefinition(
        name=name,
        enabled=enabled,
        builder=builder,
        input=raw_inputs,
        output=output,
        settings=dict(settings),
    )


def build_feature_definitions(
    cfg: Config,
) -> dict[str, FeatureDefinition]:
    features_cfg = cfg.get("features", {})

    if not isinstance(features_cfg, dict):
        raise TypeError("'features' must be a mapping")

    return {
        name: build_feature_definition(
            name=name,
            entry=entry,
        )
        for name, entry in features_cfg.items()
    }

def build_dataset_definition(
    *,
    name: str,
    entry: Any,
) -> DatasetDefinition:
    if not isinstance(entry, dict):
        raise TypeError(
            f"Dataset {name!r} must be a mapping"
        )

    builder = entry.get("builder")

    if not isinstance(builder, str) or not builder:
        raise ValueError(
            f"Dataset {name!r} must define a builder"
        )

    raw_inputs = entry.get("inputs")

    if not isinstance(raw_inputs, list) or not raw_inputs:
        raise TypeError(
            f"Inputs for dataset {name!r} must be a non-empty list"
        )

    if not all(
        isinstance(input_ref, str) and input_ref
        for input_ref in raw_inputs
    ):
        raise TypeError(
            f"Every input for dataset {name!r} "
            "must be a non-empty string"
        )

    output = entry.get("output")

    if not isinstance(output, str) or not output:
        raise ValueError(
            f"Dataset {name!r} must define an output"
        )

    enabled = entry.get("enabled", True)

    if not isinstance(enabled, bool):
        raise TypeError(
            f"'enabled' for dataset {name!r} must be a boolean"
        )

    settings = entry.get("settings", {})

    if not isinstance(settings, dict):
        raise TypeError(
            f"Settings for dataset {name!r} must be a mapping"
        )

    return DatasetDefinition(
        name=name,
        enabled=enabled,
        builder=builder,
        inputs=tuple(raw_inputs),
        output=output,
        settings=dict(settings),
    )


def build_dataset_definitions(
    cfg: Config,
) -> dict[str, DatasetDefinition]:
    datasets_cfg = cfg.get("datasets", {})

    if not isinstance(datasets_cfg, dict):
        raise TypeError("'datasets' must be a mapping")

    return {
        name: build_dataset_definition(
            name=name,
            entry=entry,
        )
        for name, entry in datasets_cfg.items()
    }

def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).resolve()
    cfg = load_yaml(config_path)

    storage_cfg = cfg.get("storage", {})

    if not isinstance(storage_cfg, dict):
        raise TypeError("'storage' must be a mapping")

    backend = storage_cfg.get("backend", "local")
    root = storage_cfg.get("root", "data")

    if not isinstance(backend, str) or not backend:
        raise TypeError("'storage.backend' must be a nonempty string")

    if not isinstance(root, str) or not root:
        raise TypeError("'storage.base_dir' must be a nonempty string")

    embeddings = cfg.get("embeddings", {})

    if not isinstance(embeddings, dict):
        raise TypeError("'embeddings' must be a mapping")

    return AppConfig(
        storage=StorageConfig(
            backend=backend,
            root=root,
        ),
        sources=build_source_definitions(
            cfg,
            config_dir=config_path.parent,
        ),
        embeddings=dict(embeddings),
        features=build_feature_definitions(cfg),
        datasets=build_dataset_definitions(cfg)
    )