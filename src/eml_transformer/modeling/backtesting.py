import pandas as pd 

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class TimeSplit:
    training: pd.DataFrame
    validation: pd.DataFrame
    training_start: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp

    
def split_latest_training_data(
    data: pd.DataFrame,
    *,
    timestamp_column: str,
    lookback_days: int,
    validation_days: int,
) -> TimeSplit:
    if timestamp_column not in data.columns:
        raise ValueError(
            f"Missing timestamp column {timestamp_column!r}"
        )

    timestamps = pd.to_datetime(
        data[timestamp_column],
        utc=True,
        errors="raise",
    )

    if timestamps.empty:
        raise ValueError("Cannot split an empty dataset")

    validation_end = timestamps.max()
    validation_start = validation_end - pd.Timedelta(
        days=validation_days
    )

    return split_training_data(
        data,
        timestamp_column=timestamp_column,
        validation_start=validation_start,
        lookback_days=lookback_days,
        validation_days=validation_days,
    )

def split_training_data(
    data: pd.DataFrame,
    *,
    timestamp_column: str,
    validation_start: pd.Timestamp,
    lookback_days: int,
    validation_days: int,
) -> TimeSplit:
    if timestamp_column not in data.columns:
        raise ValueError(
            f"Missing timestamp column {timestamp_column!r}"
        )

    if lookback_days <= 0:
        raise ValueError("lookback_days must be positive")

    if validation_days <= 0:
        raise ValueError("validation_days must be positive")

    ordered = data.copy()
    ordered[timestamp_column] = pd.to_datetime(
        ordered[timestamp_column],
        utc=True,
        errors="raise",
    )
    ordered = ordered.sort_values(timestamp_column)

    validation_start = pd.Timestamp(validation_start)

    if validation_start.tzinfo is None:
        validation_start = validation_start.tz_localize("UTC")
    else:
        validation_start = validation_start.tz_convert("UTC")

    training_start = validation_start - pd.Timedelta(
        days=lookback_days
    )
    validation_end = validation_start + pd.Timedelta(
        days=validation_days
    )

    training_data = ordered.loc[
        (ordered[timestamp_column] >= training_start)
        & (ordered[timestamp_column] < validation_start)
    ]

    validation_data = ordered.loc[
        (ordered[timestamp_column] >= validation_start)
        & (ordered[timestamp_column] < validation_end)
    ]

    if training_data.empty:
        raise ValueError(
            "No records are available in the training window"
        )

    if validation_data.empty:
        raise ValueError(
            "No records are available in the validation window"
        )

    return TimeSplit(
        training=training_data,
        validation=validation_data,
        training_start=training_start,
        validation_start=validation_start,
        validation_end=validation_end,
    )


def rolling_splits(
    data: pd.DataFrame,
    *,
    timestamp_column: str,
    lookback_days: int,
    validation_days: int,
    step_days: int,
    folds: int,
) -> list[TimeSplit]:
    if timestamp_column not in data.columns:
        raise ValueError(
            f"Missing timestamp column {timestamp_column!r}"
        )

    if step_days <= 0:
        raise ValueError("step_days must be positive")

    if folds <= 0:
        raise ValueError("folds must be positive")

    latest_time = pd.to_datetime(
        data[timestamp_column],
        utc=True,
        errors="raise",
    ).max()

    validation_duration = pd.Timedelta(
        days=validation_days
    )
    step_duration = pd.Timedelta(days=step_days)

    # The final validation window ends at or before latest_time.
    latest_validation_start = (
        latest_time - validation_duration
    )

    starts = [
        latest_validation_start - (step_duration * fold)
        for fold in reversed(range(folds))
    ]

    return [
        split_training_data(
            data,
            timestamp_column=timestamp_column,
            validation_start=start,
            lookback_days=lookback_days,
            validation_days=validation_days,
        )
        for start in starts
    ]