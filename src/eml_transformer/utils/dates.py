from datetime import date, datetime, time, timezone


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    """
    Validate that a datetime is timezone-aware and convert it to UTC.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            "Datetime must be timezone-aware"
        )

    return value.astimezone(timezone.utc)


def parse_utc_datetime(
    value: str | date | datetime,
) -> datetime:
    """
    Convert a supported value into a timezone-aware UTC datetime.

    Date values are interpreted as midnight UTC. Naive datetime
    values and strings are rejected.
    """
    if isinstance(value, datetime):
        return ensure_utc(value)

    if isinstance(value, date):
        return datetime.combine(
            value,
            time.min,
            tzinfo=timezone.utc,
        )

    if not isinstance(value, str):
        raise TypeError(
            "value must be a string, date, or datetime"
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError("Datetime string cannot be empty")

    if normalized.endswith(("Z", "z")):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            f"Invalid ISO 8601 datetime: {value!r}"
        ) from exc

    return ensure_utc(parsed)


def format_utc_datetime(
    value: str | date | datetime,
) -> str:
    """Serialize a supported value as an ISO 8601 UTC string."""
    return parse_utc_datetime(value).isoformat()