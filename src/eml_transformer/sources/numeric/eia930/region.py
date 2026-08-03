# sources/numeric/eia930/region.py

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from eml_transformer.schema.records import (
    BronzeRecord,
    NumericRecord,
)
from eml_transformer.sources.numeric.eia930.client import EIAClient


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
        client: EIAClient,
        respondent: str = "MISO",
        measurement_types: list[str] | None = None,
    ) -> None:
        self.client = client
        self.respondent = respondent.upper()
        self.measurement_types = (
            measurement_types
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
        from_date = self._ensure_utc(from_date)
        to_date = self._ensure_utc(to_date)

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
            start=self._format_api_datetime(from_date),
            end=self._format_api_datetime(to_date),
            sort_column="period",
            sort_direction="asc",
        )

        for row in rows:
            try:
                observed_at = self._parse_period(row["period"])
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

        observed_at = self._parse_period(raw["period"])
        value = self._parse_value(raw["value"])
        respondent = str(raw["respondent"]).upper()

        return NumericRecord(
            source=record.source,
            retrieved_at=record.retrieved_at,
            record_id=self._standardized_record_id(
                respondent=respondent,
                variable=variable,
                observed_at=observed_at,
            ),
            observed_at=observed_at,
            variable=variable,
            value=value,
            unit=self._normalize_unit(
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

    def _standardized_record_id(
        self,
        *,
        respondent: str,
        variable: str,
        observed_at: datetime,
    ) -> str:
        return (
            f"{self.name}:"
            f"{respondent}:"
            f"{variable}:"
            f"{observed_at.isoformat()}"
        )

    @staticmethod
    def _parse_period(value: Any) -> datetime:
        """
        EIA hourly periods use strings such as:
            2025-01-01T13

        The EIA-930 API period is treated as UTC here.
        """
        period = str(value).strip()

        try:
            parsed = datetime.strptime(
                period,
                "%Y-%m-%dT%H",
            )
        except ValueError as error:
            raise ValueError(
                f"Invalid EIA hourly period: {period!r}"
            ) from error

        return parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _parse_value(value: Any) -> float:
        if value is None:
            raise ValueError("EIA value is missing")

        normalized = str(value).replace(",", "").strip()

        if not normalized:
            raise ValueError("EIA value is empty")

        parsed = float(normalized)

        return parsed

    @staticmethod
    def _normalize_unit(value: Any) -> str:
        if value is None:
            return "unknown"

        normalized = str(value).strip().lower()

        unit_map = {
            "megawatthours": "MWh",
            "megawatt hours": "MWh",
            "mwh": "MWh",
            "megawatts": "MW",
            "mw": "MW",
        }

        return unit_map.get(normalized, str(value))

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "EIA query datetimes must be timezone-aware"
            )

        return value.astimezone(timezone.utc)

    @staticmethod
    def _format_api_datetime(value: datetime) -> str:
        return value.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H"
        )