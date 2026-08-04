from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypeAlias

from eml_transformer.utils.dates import (
    format_utc_datetime,
    parse_utc_datetime,
)


# Bronze schema
@dataclass(slots=True)
class BronzeRecord:
    source: str
    record_id: str
    published_at: datetime | None
    retrieved_at: datetime
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "record_id": self.record_id,
            "published_at": (
                format_utc_datetime(self.published_at)
                if self.published_at is not None
                else None
            ),
            "retrieved_at": format_utc_datetime(
                self.retrieved_at
            ),
            "raw": self.raw,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> BronzeRecord:
        published_at = data.get("published_at")

        return cls(
            source=data["source"],
            record_id=data["record_id"],
            published_at=(
                parse_utc_datetime(published_at)
                if published_at is not None
                else None
            ),
            retrieved_at=parse_utc_datetime(
                data["retrieved_at"]
            ),
            raw=data["raw"],
        )


# Silver text schema
@dataclass(slots=True)
class TextRecord:
    record_id: str
    source: str
    source_type: str
    title: str | None
    text: str
    published_at: datetime | None
    retrieved_at: datetime
    url: str | None = None
    region: str | None = None
    categories: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "source": self.source,
            "source_type": self.source_type,
            "title": self.title,
            "text": self.text,
            "published_at": self.published_at,
            "retrieved_at": self.retrieved_at,
            "url": self.url,
            "region": self.region,
            "categories": self.categories,
            "metadata": self.metadata,
        }


# Silver numeric schema
@dataclass(slots=True)
class NumericRecord:
    record_id: str
    source: str
    observed_at: datetime
    variable: str
    value: float
    retrieved_at: datetime
    region: str | None = None
    unit: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "source": self.source,
            # "source_type": self.source_type,
            "observed_at": self.observed_at,
            "variable": self.variable,
            "value": self.value,
            "retrieved_at": self.retrieved_at,
            "region": self.region,
            "unit": self.unit,
            "metadata": self.metadata,
        }


StandardizedRecord: TypeAlias = TextRecord | NumericRecord


TEXT_RECORD_COLUMNS = [
    "record_id",
    "source",
    "source_type",
    "title",
    "text",
    "published_at",
    "retrieved_at",
    "url",
    "region",
    "categories",
    "metadata",
]


NUMERIC_RECORD_COLUMNS = [
    "record_id",
    "source",
    "source_type",
    "observed_at",
    "variable",
    "value",
    "retrieved_at",
    "region",
    "unit",
    "metadata",
]