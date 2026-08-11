import os
from pathlib import Path
from typing import Any

import yaml


def load_config(
    path: str | Path = "configs/dev.yaml",
) -> dict[str, Any]:
    path = Path(path)

    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if cfg is None:
        raise ValueError(f"Config file is empty: {path}")

    return cfg

def build_source_config(
    source: str,
    cfg: dict[str, Any],
    config_dir: str | Path,
) -> tuple[str, dict[str, Any]]:
    sources_cfg = cfg.get("sources", {})

    if source not in sources_cfg:
        valid = ", ".join(sorted(sources_cfg))
        raise ValueError(
            f"Unknown source: {source}. "
            f"Available sources: {valid}"
        )

    source_entry = sources_cfg[source]

    if not isinstance(source_entry, dict):
        raise TypeError(
            f"Configuration for source {source!r} must be a mapping"
        )

    source_config_file = source_entry.get("config")

    if not source_config_file:
        raise ValueError(
            f"Source {source!r} does not define a config file"
        )

    source_config_path = (
        Path(config_dir) / source_config_file
    ).resolve()

    if not source_config_path.is_file():
        raise FileNotFoundError(
            f"Configuration file for source {source!r} "
            f"does not exist: {source_config_path}"
        )

    source_cfg = load_config(source_config_path)

    for component_name, component_config in source_cfg.items():
        if not isinstance(component_config, dict):
            continue

        component_config = dict(component_config)
        api_key_env = component_config.pop("api_key_env", None)

        if api_key_env:
            api_key = os.getenv(api_key_env)

            if not api_key:
                raise EnvironmentError(
                    "Missing required environment variable "
                    f"{api_key_env!r} for source {source!r}, "
                    f"component {component_name!r}"
                )

            component_config["api_key"] = api_key

        source_cfg[component_name] = component_config

    # Preserve metadata from the main configuration.
    source_cfg["enabled"] = source_entry.get("enabled", True)

    return source, source_cfg


def build_source_configs(
    cfg: dict[str, Any],
    config_dir: str | Path,
) -> dict[str, dict[str, Any]]:
    configs: dict[str, dict[str, Any]] = {}

    for source_name in cfg.get("sources", {}):
        name, source_cfg = build_source_config(
            source=source_name,
            cfg=cfg,
            config_dir=config_dir,
        )

        configs[name] = source_cfg

    return configs
