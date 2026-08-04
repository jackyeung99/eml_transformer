from datetime import datetime, timezone
from typing import Any


def parse_period(value: Any) -> datetime:
    """
    Parse an EIA-930 hourly period as a UTC datetime.

    Example:
        2025-01-01T13
    """
    period = str(value).strip()

    try:
        parsed = datetime.strptime(
            period,
            "%Y-%m-%dT%H",
        )
    except ValueError as exc:
        raise ValueError(
            f"Invalid EIA hourly period: {period!r}"
        ) from exc

    return parsed.replace(tzinfo=timezone.utc)


def parse_value(value: Any) -> float:
    """Parse an EIA numeric value."""
    if value is None:
        raise ValueError("EIA value is missing")

    normalized = str(value).replace(",", "").strip()

    if not normalized:
        raise ValueError("EIA value is empty")

    try:
        return float(normalized)
    except ValueError as exc:
        raise ValueError(
            f"Invalid EIA numeric value: {value!r}"
        ) from exc


def normalize_unit(value: Any) -> str:
    """Normalize an EIA unit name."""
    if value is None:
        return "unknown"

    normalized = str(value).strip().lower()

    unit_map = {
        "megawatthours": "MWh",
        "megawatt hours": "MWh",
        "mwh": "MWh",
        "megawatts": "MW",
        "megawatt": "MW",
        "mw": "MW",
    }

    return unit_map.get(
        normalized,
        str(value).strip(),
    )