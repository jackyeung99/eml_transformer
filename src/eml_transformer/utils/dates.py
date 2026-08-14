from __future__ import annotations

from datetime import date, datetime, time, timezone


UTC = timezone.utc

DateLike = str | date | datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Validate that a datetime is aware and convert it to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime must be timezone-aware")

    return value.astimezone(UTC)


def parse_utc_datetime(value: DateLike) -> datetime:
    """Convert a supported value into an aware UTC datetime."""
    if isinstance(value, datetime):
        parsed = value

    elif isinstance(value, date):
        parsed = datetime.combine(
            value,
            time.min,
            tzinfo=UTC,
        )

    elif isinstance(value, str):
        parsed = datetime.fromisoformat(
            value.strip().replace("Z", "+00:00")
        )

    else:
        raise TypeError(
            "Expected a string, date, or datetime, "
            f"received {type(value).__name__!r}"
        )

    # Treat naive values as UTC.
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


def parse_optional_utc_datetime(
    value: DateLike | None,
) -> datetime | None:
    if value is None:
        return None

    return parse_utc_datetime(value)


def format_utc_datetime(value: datetime) -> str:
    """Serialize a datetime as an ISO 8601 UTC string."""
    return ensure_utc(value).isoformat()


def format_optional_utc_datetime(
    value: datetime | None,
) -> str | None:
    if value is None:
        return None

    return format_utc_datetime(value)