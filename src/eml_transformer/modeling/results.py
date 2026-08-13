# modeling/results.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Status = Literal["success", "failure", "skipped"]


@dataclass(slots=True)
class TrainingResult:
    status: Status
    name: str
    records_read: int = 0
    model_ref: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    error: str | None = None

    def to_summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "records": self.records_read,
            "model": self.model_ref,
            **self.metrics,
            "error": self.error,
        }


@dataclass(slots=True)
class ForecastResult:
    status: Status
    name: str
    records_read: int = 0
    records_written: int = 0
    model_ref: str | None = None
    output_ref: str | None = None
    error: str | None = None

    def to_summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "read": self.records_read,
            "written": self.records_written,
            "model": self.model_ref,
            "output": self.output_ref,
            "error": self.error,
        }


@dataclass(slots=True)
class BacktestResult:
    status: Status
    name: str
    folds_completed: int = 0
    predictions_written: int = 0
    metrics: dict[str, float] = field(default_factory=dict)
    output_ref: str | None = None
    error: str | None = None

    def to_summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "folds": self.folds_completed,
            "predictions": self.predictions_written,
            **self.metrics,
            "output": self.output_ref,
            "error": self.error,
        }


@dataclass(slots=True)
class ExperimentResult:
    status: Status
    name: str
    candidates_evaluated: int = 0
    best_candidate: str | None = None
    best_metrics: dict[str, float] = field(default_factory=dict)
    output_ref: str | None = None
    error: str | None = None

    def to_summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "candidates": self.candidates_evaluated,
            "best_candidate": self.best_candidate,
            **{
                f"best_{metric}": value
                for metric, value in self.best_metrics.items()
            },
            "output": self.output_ref,
            "error": self.error,
        }