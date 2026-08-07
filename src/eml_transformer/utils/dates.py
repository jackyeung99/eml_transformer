from datetime import date, datetime, time, timezone

UTC = timezone.utc
from zoneinfo import ZoneInfo
from dateutil.parser import isoparse


DateLike = str | date | datetime



def utc_now() -> datetime:
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



def format_utc_datetime(value: datetime) -> str:
    """Serialize a datetime as an ISO 8601 UTC string."""
    return parse_utc_datetime(value).isoformat()



def parse_utc_datetime(value: str | date | datetime) -> datetime:
    """Convert supported input into a timezone-aware UTC datetime."""
    if isinstance(value, datetime):
        parsed = value

    elif isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=UTC)

    else:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)

    if parsed.tzinfo is UTC:
        return parsed

    return parsed.astimezone(UTC)