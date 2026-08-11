from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.storage import Storage, make_storage
from eml_transformer.utils.config import (
    build_source_configs,
    load_config,
)


Config = dict[str, Any]
ConfigMap = dict[str, Config]


@dataclass(slots=True)
class Runtime:
    storage: Storage
    paths: StoragePaths

    source_configs: ConfigMap
    enabled_source_names: tuple[str, ...]

    feature_configs: ConfigMap
    embedding_config: Config

    @property
    def source_names(self) -> list[str]:
        return list(self.source_configs)

    @property
    def enabled_source_configs(self) -> ConfigMap:
        return {
            name: self.source_configs[name]
            for name in self.enabled_source_names
        }

    @property
    def feature_names(self) -> list[str]:
        return list(self.feature_configs)

    @property
    def enabled_feature_names(self) -> list[str]:
        return [
            name
            for name, config in self.feature_configs.items()
            if config.get("enabled", True)
        ]

    @property
    def enabled_feature_configs(self) -> ConfigMap:
        return {
            name: self.feature_configs[name]
            for name in self.enabled_feature_names
        }


def build_runtime(config_path: str | Path) -> Runtime:
    config_path = Path(config_path).resolve()
    cfg = load_config(config_path)

    paths = StoragePaths(
        root=cfg.get("paths", {}).get("root", "."),
    )

    storage = make_storage(
        cfg["storage"],
        paths=paths,
    )

    source_configs = build_source_configs(
        cfg=cfg,
        config_dir=config_path.parent,
    )

    enabled_source_names = tuple(
        name
        for name, source_entry in cfg.get("sources", {}).items()
        if source_entry.get("enabled", True)
    )

    return Runtime(
        storage=storage,
        paths=paths,
        source_configs=source_configs,
        enabled_source_names=enabled_source_names,
        feature_configs=cfg.get("features", {}),
        embedding_config=cfg.get("embeddings", {}),
    )