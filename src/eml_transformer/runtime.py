
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.storage import Storage, make_storage
from eml_transformer.utils.config import (
    build_source_configs,
    load_config,
)


@dataclass
class Runtime:
    cfg: dict
    storage: Storage
    paths: StoragePaths
    source_configs: dict[str, dict]

    @property
    def source_names(self) -> list[str]:
        """All configured sources."""
        return list(self.source_configs)

    @property
    def enabled_source_names(self) -> list[str]:
        """Sources included in run-all."""
        return [
            name
            for name, source_cfg in self.cfg.get(
                "sources",
                {},
            ).items()
            if source_cfg.get("enabled", True)
        ]

    @property
    def ingestion_config(self) -> dict:
        return self.cfg.get("ingestion", {})

    @property
    def standardization_config(self) -> dict:
        return self.cfg.get("standardization", {})

    @property
    def embedding_config(self) -> dict:
        return self.cfg.get("embeddings", {})


def build_runtime(
    config_path: str | Path,
) -> Runtime:
    config_path = Path(config_path).resolve()
    cfg = load_config(config_path)

    storage = make_storage(cfg["storage"])

    paths = StoragePaths(
        root=cfg.get("paths", {}).get("root", "."),
    )

    source_configs = build_source_configs(
        cfg=cfg,
        config_dir=config_path.parent,
    )

    return Runtime(
        cfg=cfg,
        storage=storage,
        paths=paths,
        source_configs=source_configs,
    )