from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from eml_transformer.utils.config import (
    AppConfig,
    SourceDefinition,
    FeatureDefinition,
    load_config,
)
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.storage import Storage, make_storage


logger = logging.getLogger(__name__)

SOURCE_STAGES = frozenset(
    {
        "ingest",
        "backfill",
        "standardize",
        "scrape",
        "embed",
    }
)


@dataclass(slots=True)
class Runtime:
    config: AppConfig
    storage: Storage
    paths: StoragePaths

    @property
    def source_names(self) -> tuple[str, ...]:
        return tuple(self.config.sources)

    @property
    def enabled_source_names(self) -> tuple[str, ...]:
        return tuple(
            source.name
            for source in self.config.sources.values()
            if source.enabled
        )

    @property
    def embedding_config(self) -> dict[str, object]:
        return dict(self.config.embeddings)

    def get_source(self, name: str) -> SourceDefinition:
        try:
            return self.config.sources[name]
        except KeyError as exc:
            available = ", ".join(sorted(self.config.sources))

            raise ValueError(
                f"Unknown source {name!r}. "
                f"Available sources: {available}"
            ) from exc

    def sources_for_stage(
        self,
        stage: str,
        *,
        requested: str = "all",
    ) -> list[SourceDefinition]:
        """
        Resolve the sources that a CLI command should execute.

        `all` returns enabled sources that support the stage.

        An explicitly named source may be disabled, but it must support
        the requested stage.
        """
        if stage not in SOURCE_STAGES:
            available = ", ".join(sorted(SOURCE_STAGES))

            raise ValueError(
                f"Unknown stage {stage!r}. "
                f"Available stages: {available}"
            )

        if requested.lower() == "all":
            return [
                source
                for source in self.config.sources.values()
                if source.enabled and stage in source.stages
            ]

        source = self.get_source(requested)

        if stage not in source.stages:
            supported = ", ".join(sorted(source.stages)) or "none"

            raise ValueError(
                f"Source {source.name!r} does not support "
                f"stage {stage!r}. Supported stages: {supported}"
            )

        if not source.enabled:
            logger.warning(
                "Running disabled source=%s because it was "
                "explicitly requested",
                source.name,
            )

        return [source]

    def effective_embedding_config(
        self,
        source: SourceDefinition,
        *,
        model_name: str | None = None,
    ) -> dict[str, object]:
        """
        Merge global embedding settings with source-level overrides.
        """
        config = {
            **self.config.embeddings,
            **source.settings.get("embedding", {}),
        }

        if model_name is not None:
            config["model"] = model_name

        return config

    def features(
        self,
        requested: str = "all",
    ) -> list[FeatureDefinition]:
        if requested.lower() == "all":
            return [
                feature
                for feature in self.config.features.values()
                if feature.enabled
            ]

        try:
            feature = self.config.features[requested]
        except KeyError as exc:
            available = ", ".join(sorted(self.config.features))

            raise ValueError(
                f"Unknown feature {requested!r}. "
                f"Available features: {available}"
            ) from exc

        if not feature.enabled:
            logger.warning(
                "Running disabled feature=%s because it was "
                "explicitly requested",
                feature.name,
            )

        return [feature]

def build_runtime(config_path: str | Path) -> Runtime:
    config = load_config(config_path)

    paths = StoragePaths()

    storage = make_storage(
        config.storage,
        paths=paths,
    )

    return Runtime(
        config=config,
        paths=paths,
        storage=storage,
    )