import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

DAY_TYPE_MAP = {
    0: "weekday",  # Monday
    1: "weekday",
    2: "weekday",
    3: "weekday",
    4: "weekday",  # Friday
    5: "weekend",  # Saturday
    6: "weekend",  # Sunday
}


def add_calendar_features(
    df: pd.DataFrame,
    *,
    time_column: str = "observed_at",
) -> pd.DataFrame:
    """
    Add calendar features derived from a timestamp column.
    """
    if time_column not in df.columns:
        raise KeyError(f"Missing time column: {time_column!r}")

    result = df.copy()
    timestamps = pd.to_datetime(result[time_column], utc=True)

    result["hour"] = timestamps.dt.hour
    result["day_of_week"] = timestamps.dt.dayofweek
    result["day_name"] = timestamps.dt.day_name()
    result["day_type"] = result["day_of_week"].map(DAY_TYPE_MAP)
    result["month"] = timestamps.dt.month
    result["is_weekend"] = result["day_type"].eq("weekend")

    return result

def add_holiday_feature(
    df: pd.DataFrame,
    *,
    time_column: str = "observed_at",
    timezone: str = "America/Chicago",
) -> pd.DataFrame:
    """
    Add an is_holiday indicator based on observed US federal holidays.

    The timestamp is converted to local time before its calendar date
    is compared against the holiday calendar.
    """
    if time_column not in df.columns:
        raise KeyError(f"Missing time column: {time_column!r}")

    result = df.copy()

    timestamps = pd.to_datetime(
        result[time_column],
        utc=True,
        errors="raise",
    ).dt.tz_convert(timezone)

    local_dates = timestamps.dt.normalize().dt.tz_localize(None)

    calendar = USFederalHolidayCalendar()
    holidays = calendar.holidays(
        start=local_dates.min(),
        end=local_dates.max(),
    )

    result["is_holiday"] = local_dates.isin(holidays)

    return result


def add_local_timestamp(
    df: pd.DataFrame,
    *,
    source_column: str = "observed_at",
    output_column: str = "observed_at_eta",
    timezone: str = "America/New_York",
) -> pd.DataFrame:
    """
    Add a timezone-aware local timestamp while preserving the original column.

    America/New_York automatically handles EST and EDT.
    """
    if source_column not in df.columns:
        raise KeyError(f"Missing timestamp column: {source_column!r}")

    result = df.copy()

    result[output_column] = (
        pd.to_datetime(
            result[source_column],
            utc=True,
            errors="raise",
        )
        .dt.tz_convert(timezone)
    )

    return result