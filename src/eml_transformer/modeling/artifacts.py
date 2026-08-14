from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from eml_transformer.utils.dates import (
    format_optional_utc_datetime,
    format_utc_datetime,
    parse_optional_utc_datetime,
    parse_utc_datetime,
    ensure_utc,
)


def build_model_version(
    trained_at: datetime,
) -> str:
    trained_at = ensure_utc(trained_at)

    return trained_at.strftime(
        "%Y%m%dT%H%M%S.%fZ"
    )

@dataclass(frozen=True, slots=True)
class ModelMetadata:
    name: str
    model_type: str
    model_version: str
    trained_at: datetime

    features: tuple[str, ...]
    target: str

    records_used: int
    records_trained: int
    records_validated: int

    hyper_parameters: dict[str, Any]
    training_settings: dict[str, Any]

    metrics: dict[str, float]
    diagnostics: dict[str, Any]

    training_start: datetime | None = None
    training_end: datetime | None = None
    validation_start: datetime | None = None
    validation_end: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "model_type": self.model_type,
            "model_version": self.model_version,
            "trained_at": format_utc_datetime(
                self.trained_at
            ),
            "features": list(self.features),
            "target": self.target,
            "records_used": self.records_used,
            "records_trained": self.records_trained,
            "records_validated": self.records_validated,
            "hyper_parameters": dict(
                self.hyper_parameters
            ),
            "training_settings": dict(
                self.training_settings
            ),
            "metrics": dict(self.metrics),
            "diagnostics": dict(self.diagnostics),
            "training_start": (
                format_optional_utc_datetime(
                    self.training_start
                )
            ),
            "training_end": (
                format_optional_utc_datetime(
                    self.training_end
                )
            ),
            "validation_start": (
                format_optional_utc_datetime(
                    self.validation_start
                )
            ),
            "validation_end": (
                format_optional_utc_datetime(
                    self.validation_end
                )
            ),
        }

    @classmethod
    def from_dict(
        cls,
        values: Mapping[str, Any],
    ) -> ModelMetadata:

        trained_at = _required_utc_datetime(
            values,
            "trained_at",
        )


        return cls(
            name=str(values["name"]),
            model_type=str(values["model_type"]),
            model_version=str(
                values.get(
                    "model_version",
                    build_model_version(trained_at),
                )
            ),
            trained_at=trained_at,
                features=tuple(
                    str(feature)
                    for feature in values["features"]
                ),
            target=str(values["target"]),
            records_used=int(values["records_used"]),
            records_trained=int(
                values["records_trained"]
            ),
            records_validated=int(
                values["records_validated"]
            ),
            hyper_parameters=_dictionary(
                values.get("hyper_parameters")
            ),
            training_settings=_dictionary(
                values.get("training_settings")
            ),
            metrics={
                str(name): float(value)
                for name, value in _dictionary(
                    values.get("metrics")
                ).items()
            },
            diagnostics=_dictionary(
                values.get("diagnostics")
            ),
            training_start=(
                parse_optional_utc_datetime(
                    values.get("training_start")
                )
            ),
            training_end=(
                parse_optional_utc_datetime(
                    values.get("training_end")
                )
            ),
            validation_start=(
                parse_optional_utc_datetime(
                    values.get("validation_start")
                )
            ),
            validation_end=(
                parse_optional_utc_datetime(
                    values.get("validation_end")
                )
            ),
        )


def _required_utc_datetime(
    values: Mapping[str, Any],
    field: str,
) -> datetime:
    value = values.get(field)

    if value is None:
        raise ValueError(
            f"Model metadata requires {field!r}"
        )

    return parse_utc_datetime(value)


def _dictionary(
    value: Any,
) -> dict[str, Any]:
    if value is None:
        return {}

    if not isinstance(value, Mapping):
        raise TypeError(
            "Expected a metadata mapping, "
            f"received {type(value).__name__!r}"
        )

    return {
        str(key): item
        for key, item in value.items()
    }