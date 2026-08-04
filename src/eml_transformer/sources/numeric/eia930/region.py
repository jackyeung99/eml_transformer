from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

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



@register_source("eia_region")
class EIA930RegionSource:
    """
    Hourly balancing-authority operating data from EIA-930.

    EIA route:
        electricity/rto/region-data

    Variables:
        D  -> actual_load
        DF -> load_forecast
        NG -> net_generation
        TI -> total_interchange
    """

    name = "eia930_region"
    source_type = "numeric"

    update_mode = "incremental"
    supports_backfill = True
    default_lookback_days = 3

    route = "electricity/rto/region-data"

    variable_map = {
        "D": "actual_load",
        "DF": "load_forecast",
        "NG": "net_generation",
        "TI": "total_interchange",
    }

    def __init__(
        self,
        client: EIAClient | None = None,
        *,
        api_key: str | None = None,
        respondent: str = "MISO",
        measurement_types: list[str] | None = None,
    ) -> None:
        if client is not None and api_key is not None:
            raise ValueError(
                "Pass either client or api_key, not both"
            )

        self.client = (
            client
            if client is not None
            else EIAClient(api_key=api_key)
        )

        self.respondent = respondent.upper()
        self.measurement_types = (
            list(measurement_types)
            if measurement_types is not None
            else ["D", "DF", "NG", "TI"]
        )

        invalid_types = (
            set(self.measurement_types)
            - set(self.variable_map)
        )

        if invalid_types:
            raise ValueError(
                "Unsupported EIA-930 region measurement types: "
                f"{sorted(invalid_types)}"
            )

    def fetch_records(
        self,
        from_date: datetime,
        to_date: datetime,
    ) -> Iterator[BronzeRecord]:
        """
        Retrieve raw EIA rows for an inclusive UTC date range.

        Pagination is handled by EIAClient.iter_data().
        """
        from_date = ensure_utc(from_date)
        to_date = ensure_utc(to_date)

        if from_date > to_date:
            raise ValueError("from_date must not be after to_date")

        retrieved_at = datetime.now(timezone.utc)

        rows = self.client.iter_data(
            route=self.route,
            data=["value"],
            facets={
                "respondent": [self.respondent],
                "type": self.measurement_types,
            },
            frequency="hourly",
            start=from_date,
            end=to_date,
            sort_column="period",
            sort_direction="asc",
        )

        for row in rows:
            try:
                observed_at = parse_period(row["period"])
                measurement_code = str(row["type"])

                yield BronzeRecord(
                    source=self.name,
                    record_id=self._bronze_record_id(
                        row=row,
                    ),
                    published_at=observed_at,
                    retrieved_at=retrieved_at,
                    raw=dict(row),
                )
            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                # Let the ingestion pipeline track failed rows if it
                # already provides per-record error handling.
                raise

    def standardize_record(
        self,
        record: BronzeRecord,
    ) -> NumericRecord:
        """
        Convert one bronze EIA-930 record into a NumericRecord.
        """
        raw = record.raw

        measurement_code = str(raw["type"])
        variable = self.variable_map.get(measurement_code)

        if variable is None:
            raise ValueError(
                "Unsupported EIA-930 measurement type: "
                f"{measurement_code!r}"
            )

        observed_at = parse_period(raw["period"])
        value = parse_value(raw["value"])
        respondent = str(raw["respondent"]).upper()

        return NumericRecord(
            source=record.source,
            retrieved_at=record.retrieved_at,
            record_id=record.record_id,
            observed_at=observed_at,
            variable=variable,
            value=value,
            unit=normalize_unit(
                raw.get("value-units")
            ),
            region=respondent,
            metadata={
                "provider": "EIA",
                "dataset": "EIA-930",
                "route": self.route,
                "respondent": respondent,
                "respondent_name": raw.get("respondent-name"),
                "measurement_code": measurement_code,
                "measurement_name": raw.get("type-name"),
                "time_resolution": "hourly",
                "original_period": raw["period"],
                "original_unit": raw.get("value-units"),
                "bronze_record_id": record.record_id,
                "retrieved_at": record.retrieved_at.isoformat(),
            },
        )
    
    def _bronze_record_id(
        self,
        row: dict[str, Any],
    ) -> str:
        return (
            f"{self.name}:"
            f"{row['respondent']}:"
            f"{row['type']}:"
            f"{row['period']}"
        )