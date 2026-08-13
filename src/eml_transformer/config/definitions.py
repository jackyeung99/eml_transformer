from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


Config = dict[str, Any]

'''
Dataclasses are used to add more structure to inputs of pipeline stages. Before this 
they would take in a generic dictionary defining the configuration of that stage, Moving to 
dataclasses improves robustness so that stages do not have to guess at what input they get.
'''

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
    settings: Config = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    name: str
    enabled: bool
    builder: str
    input: str
    output: str
    settings: Config = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DatasetDefinition:
    name: str
    enabled: bool
    builder: str
    inputs: dict[str, str]
    output: str
    settings: Config = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelingDefinition:
    name: str
    enabled: bool
    trainer: str
    training_input: str
    forecast_input: str
    model_output: str
    forecast_output: str
    target: str
    features: tuple[str, ...]
    settings: Config = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class ExperimentDefinition:
    name: str

@dataclass(frozen=True, slots=True)
class AppConfig:
    storage: StorageConfig
    sources: dict[str, SourceDefinition]
    embeddings: Config
    features: dict[str, FeatureDefinition]
    datasets: dict[str, DatasetDefinition]
    models: dict[str, ModelingDefinition]