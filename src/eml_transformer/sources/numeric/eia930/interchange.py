from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any, Literal

from eml_transformer.schema.records import (
    BronzeRecord,
    NumericRecord,
)
from eml_transformer.utils.dates import ensure_utc
from eml_transformer.sources.numeric.eia930.client import EIAClient
from eml_transformer.sources.registry import register_source

from eml_transformer.sources.numeric.eia930.parsing import (
    parse_period, 
    parse_value,
    normalize_unit
)

@register_source("eia_interchange")
class EIA930InterchangeSource:
    """
    Hourly directional interchange between balancing authorities.

    EIA route:
        electricity/rto/interchange-data

    Natural grain:
        period × fromba × toba
    """

    name = "eia930_interchange"
    source_type = "numeric"

    update_mode = "incremental"
    supports_backfill = True
    default_lookback_days = 3

    route = "electricity/rto/interchange-data"

    def __init__(
        self,
        client: EIAClient | None = None,
        *,
        api_key: str | None = None,
        balancing_authority: str = "MISO",
        neighbors: list[str] | None = None,
        direction: Literal[
            "outbound",
            "inbound",
            "both",
        ] = "both",
    ) -> None:
        if client is not None and api_key is not None:
            raise ValueError(
                "Pass either client or api_key, not both"
            )

        if direction not in {
            "outbound",
            "inbound",
            "both",
        }:
            raise ValueError(
                "direction must be outbound, inbound, or both"
            )

        self.client = (
            client
            if client is not None
            else EIAClient(api_key=api_key)
        )

        self.balancing_authority = (
            balancing_authority.upper()
        )
        self.neighbors = (
            [neighbor.upper() for neighbor in neighbors]
            if neighbors is not None
            else None
        )
        self.direction = direction

    def fetch_records(
        self,
        from_date: datetime,
        to_date: datetime,
    ) -> Iterator[BronzeRecord]:
        from_date = ensure_utc(from_date)
        to_date = ensure_utc(to_date)

        if from_date > to_date:
            raise ValueError(
                "from_date must not be after to_date"
            )

        retrieved_at = datetime.now(timezone.utc)

        for facets in self._build_queries():
            rows = self.client.iter_data(
                route=self.route,
                data=["value"],
                facets=facets,
                frequency="hourly",
                start=from_date,
                end=to_date,
                sort_column="period",
                sort_direction="asc",
            )

            for row in rows:
                observed_at = parse_period(
                    row["period"]
                )

                yield BronzeRecord(
                    source=self.name,
                    record_id=self._bronze_record_id(row),
                    published_at=observed_at,
                    retrieved_at=retrieved_at,
                    raw=dict(row),
                )

    def standardize_record(
        self,
        record: BronzeRecord,
    ) -> NumericRecord:
        raw = record.raw

        observed_at = parse_period(raw["period"])
        from_region = str(raw["fromba"]).upper()
        to_region = str(raw["toba"]).upper()
        value = parse_value(raw["value"])

        return NumericRecord(
            source=record.source,
            retrieved_at=record.retrieved_at,
            record_id=record.record_id,
            observed_at=observed_at,
            variable="interchange",
            value=value,
            unit=normalize_unit(
                raw.get("value-units")
            ),
            region=self.balancing_authority,
            metadata={
                "provider": "EIA",
                "dataset": "EIA-930",
                "route": self.route,
                "from_region": from_region,
                "from_region_name": raw.get("fromba-name"),
                "to_region": to_region,
                "to_region_name": raw.get("toba-name"),
                "time_resolution": "hourly",
                "original_period": raw["period"],
                "original_unit": raw.get("value-units"),
                "bronze_record_id": record.record_id,
            },
        )

    def _build_queries(
        self,
    ) -> list[dict[str, list[str]]]:
        queries: list[dict[str, list[str]]] = []

        if self.direction in {"outbound", "both"}:
            outbound = {
                "fromba": [self.balancing_authority],
            }

            if self.neighbors:
                outbound["toba"] = self.neighbors

            queries.append(outbound)

        if self.direction in {"inbound", "both"}:
            inbound = {
                "toba": [self.balancing_authority],
            }

            if self.neighbors:
                inbound["fromba"] = self.neighbors

            queries.append(inbound)

        return queries

    def _bronze_record_id(
        self,
        row: dict[str, Any],
    ) -> str:
        return (
            f"{self.name}:"
            f"{str(row['fromba']).upper()}:"
            f"{str(row['toba']).upper()}:"
            f"{row['period']}"
        )
