# modeling/results.py

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


Status = Literal["success", "failure", "skipped"]

'''
All the other pipeline steps has the Result with the pipeline but since the Modeling Pipeline 
has multiple methods (Train, Forecast, and Experiment) I have created a new file for it, My hope is that it improves 
readibility. 
'''

@dataclass(slots=True)
class TrainingResult:
    status: str
    name: str

    reason: str | None = None
    error: str | None = None

    records_read: int = 0
    records_used: int = 0
    records_trained: int = 0
    records_validated: int = 0

    model_ref: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    trained_at: datetime | None = None

    def to_summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "reason": self.reason,
            "records_read": self.records_read,
            "records_used": self.records_used,
            "records_trained": self.records_trained,
            "records_validated": self.records_validated,
            "model": self.model_ref,
            "trained_at": (
                self.trained_at.isoformat()
                if self.trained_at is not None
                else None
            ),
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