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
) -> tuple[str, dict[str, Any]]:
    """
    Resolve API keys for each configured source stage.

    Each source may contain separate configuration sections for stages such as
    ingestion and standardization. A stage requiring an API key should define
    `api_key_env`, whose value is the name of an environment variable containing
    the key.

    The resolved key is added to that stage's configuration as `api_key`, and
    `api_key_env` is removed. The API key itself should never be stored directly
    in the configuration file.
    """
    sources_cfg = cfg.get("sources", {})

    if source not in sources_cfg:
        valid = ", ".join(sources_cfg)
        raise ValueError(
            f"Unknown source: {source}. Available sources: {valid}"
        )

    source_cfg = dict(sources_cfg[source])
    source_cfg.pop("enabled", None)

    for component_name, component_config in source_cfg.items():
        if not isinstance(component_config, dict):
            continue

        component_config = dict(component_config)
        api_key_env = component_config.pop("api_key_env", None)

        if api_key_env:
            api_key = os.getenv(api_key_env)

            if not api_key:
                raise EnvironmentError(
                    f"Missing required environment variable: {api_key_env}"
                )

            component_config["api_key"] = api_key

        source_cfg[component_name] = component_config

    return source, source_cfg


def build_source_configs(
    cfg: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    configs = {}

    for source_name, source_cfg in cfg.get(
        "sources",
        {},
    ).items():

        if not source_cfg.get(
            "enabled",
            True,
        ):
            continue

        name, kwargs = build_source_config(
            source_name,
            cfg,
        )

        configs[name] = kwargs

    return configs