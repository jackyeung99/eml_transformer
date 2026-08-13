from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    name: str
    model_type: str
    trained_at: datetime

    features: tuple[str, ...]
    target: str

    records_used: int
    records_trained: int
    records_validated: int

    hyper_parameters: dict[str, Any]
    training_settings: dict[str, Any]
    metrics: dict[str, float]

    training_start: datetime | None = None
    validation_start: datetime | None = None
    validation_end: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "model_type": self.model_type,
            "trained_at": self.trained_at.isoformat(),
            "features": list(self.features),
            "target": self.target,
            "records_used": self.records_used,
            "records_trained": self.records_trained,
            "records_validated": self.records_validated,
            "hyper_parameters": dict(self.hyper_parameters),
            "training_settings": dict(self.training_settings),
            "metrics": dict(self.metrics),
            "training_start": _datetime_to_string(
                self.training_start
            ),
            "validation_start": _datetime_to_string(
                self.validation_start
            ),
            "validation_end": _datetime_to_string(
                self.validation_end
            ),
        }

    @classmethod
    def from_dict(
        cls,
        values: Mapping[str, Any],
    ) -> ModelMetadata:
        return cls(
            name=str(values["name"]),
            model_type=str(values["model_type"]),
            trained_at=_required_datetime(
                values,
                "trained_at",
            ),
            features=tuple(
                str(feature)
                for feature in values["features"]
            ),
            target=str(values["target"]),
            records_used=int(values["records_used"]),
            records_trained=int(values["records_trained"]),
            records_validated=int(
                values["records_validated"]
            ),
            hyper_parameters=dict(
                values.get("hyper_parameters", {})
            ),
            training_settings=dict(
                values.get("training_settings", {})
            ),
            metrics={
                str(metric): float(value)
                for metric, value in dict(
                    values.get("metrics", {})
                ).items()
            },
            training_start=_optional_datetime(
                values.get("training_start")
            ),
            validation_start=_optional_datetime(
                values.get("validation_start")
            ),
            validation_end=_optional_datetime(
                values.get("validation_end")
            ),
        )


def _datetime_to_string(
    value: datetime | None,
) -> str | None:
    return value.isoformat() if value is not None else None


def _optional_datetime(
    value: Any,
) -> datetime | None:
    if value is None:
        return None

    return datetime.fromisoformat(str(value))


def _required_datetime(
    values: Mapping[str, Any],
    field: str,
) -> datetime:
    value = _optional_datetime(values.get(field))

    if value is None:
        raise ValueError(
            f"Model metadata requires {field!r}"
        )

    return value