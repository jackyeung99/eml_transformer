from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class IngestionResult:
    status: str
    source: str
    records_fetched: int = 0
    records_written: int = 0
    records_skipped: int = 0
    # records_failed: int = 0 # can add later but each source needs to propagate this 
    from_date: datetime | None = None
    to_date: datetime | None = None
    bronze_key: str | None = None
    dedupe_key: str | None = None
    reason: str | None = None
    error: str | None = None

    def to_summary(self) -> dict[str, object]:
        summary: dict[str, object] = {
            "source": self.source,
            "status": self.status,
            "from": self.from_date,
            "to": self.to_date,
            "fetched": self.records_fetched,
            "written": self.records_written,
            "skipped": self.records_skipped,
        }

        if self.reason:
            summary["reason"] = self.reason

        if self.error:
            summary["error"] = self.error

        return summary

@dataclass
class BackfillResult:
    status: str
    source: str
    from_date: datetime
    to_date: datetime
    window_days: int
    windows_total: int
    windows_completed: int
    records_fetched: int
    records_written: int
    records_skipped: int
    records_failed: int = 0
    reason: str | None = None
    error: str | None = None

    def to_summary(self) -> dict[str, object]:
        summary: dict[str, object] = {
            "source": self.source,
            "status": self.status,
            "from": self.from_date,
            "to": self.to_date,
            "windows": (
                f"{self.windows_completed}/{self.windows_total}"
            ),
            "fetched": self.records_fetched,
            "written": self.records_written,
            "skipped": self.records_skipped,
            "failed": self.records_failed,
        }

        if self.reason:
            summary["reason"] = self.reason

        if self.error:
            summary["error"] = self.error

        return summary