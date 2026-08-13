from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    name: str
    architecture: str
    input_ref: str
    trained_at: datetime
    features: tuple[str, ...]
    target: str
    records_trained: int
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "architecture": self.architecture,
            "input_ref": self.input_ref,
            "trained_at": self.trained_at.isoformat(),
            "features": list(self.features),
            "target": self.target,
            "records_trained": self.records_trained,
            "parameters": self.parameters,
        }

    @classmethod
    def from_dict(
        cls,
        values: dict[str, Any],
    ) -> ModelMetadata:
        return cls(
            name=str(values["name"]),
            architecture=str(values["architecture"]),
            input_ref=str(values["input_ref"]),
            trained_at=datetime.fromisoformat(
                str(values["trained_at"])
            ),
            features=tuple(values["features"]),
            target=str(values["target"]),
            records_trained=int(values["records_trained"]),
            parameters=dict(values.get("parameters", {})),
        )