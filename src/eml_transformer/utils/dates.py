from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo
from dateutil.parser import isoparse


DateLike = str | date | datetime



def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def format_utc_datetime(value: datetime) -> str:
    """Serialize a datetime as an ISO 8601 UTC string."""
    return parse_utc_datetime(value).isoformat()

def parse_utc_datetime(value: str | date | datetime) -> datetime:
    """Convert supported input into a timezone-aware UTC datetime."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    else:
        parsed = isoparse(value.strip())

    if parsed.tzinfo is None:
        # Existing naive values are interpreted as UTC.
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)

    return parsed
