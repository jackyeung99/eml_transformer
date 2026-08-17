from datetime import datetime
from typing import Any, TypeAlias
from dataclasses import dataclass, field

@dataclass(frozen=True)
class ForecastRecord:
    issued_at: datetime
    target_at: datetime
    horizon_hours: int
    predicted_value: float

    model_name: str
    model_version: str
    series_id: str       # e.g. MISO load
    run_id: str