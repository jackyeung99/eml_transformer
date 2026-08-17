from dataclasses import dataclass

import pandas as pd

from eml_transformer.utils.dates import ensure_utc


@dataclass(frozen=True, slots=True)
class TimeSplit:
    training: pd.DataFrame
    validation: pd.DataFrame

    training_start: pd.Timestamp
    training_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp


def _prepare_time_data(
    data: pd.DataFrame,
    *,
    timestamp_column: str,
) -> pd.DataFrame:
    if timestamp_column not in data.columns:
        raise ValueError(
            f"Missing timestamp column {timestamp_column!r}"
        )

    if data.empty:
        raise ValueError("Cannot split an empty dataset")

    prepared = data.copy()
    prepared[timestamp_column] = pd.to_datetime(
        prepared[timestamp_column],
        utc=True,
        errors="raise",
    )

    if prepared[timestamp_column].isna().any():
        raise ValueError(
            f"Column {timestamp_column!r} contains missing timestamps"
        )

    return prepared.sort_values(timestamp_column)


def split_training_data(
    data: pd.DataFrame,
    *,
    timestamp_column: str,
    validation_start: pd.Timestamp,
    validation_end: pd.Timestamp,
    lookback_days: int,
) -> TimeSplit:
    if lookback_days <= 0:
        raise ValueError("lookback_days must be positive")

    ordered = _prepare_time_data(
        data,
        timestamp_column=timestamp_column,
    )

    validation_start = ensure_utc(validation_start)
    validation_end = ensure_utc(validation_end)

    if validation_end <= validation_start:
        raise ValueError(
            "validation_end must be after validation_start"
        )

    training_window_start = (
        validation_start
        - pd.Timedelta(days=lookback_days)
    )

    timestamps = ordered[timestamp_column]

    # Half-open windows:
    # training:   [training_window_start, validation_start)
    # validation: [validation_start, validation_end)
    training_data = ordered.loc[
        (timestamps >= training_window_start)
        & (timestamps < validation_start)
    ].copy()

    validation_data = ordered.loc[
        (timestamps >= validation_start)
        & (timestamps < validation_end)
    ].copy()

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
        # Store actual observed boundaries, not requested boundaries.
        training_start=training_data[timestamp_column].min(),
        training_end=training_data[timestamp_column].max(),
        validation_start=validation_data[timestamp_column].min(),
        validation_end=validation_data[timestamp_column].max(),
    )


def split_latest_training_data(
    data: pd.DataFrame,
    *,
    timestamp_column: str,
    lookback_days: int,
    validation_days: int,
) -> TimeSplit:
    if validation_days <= 0:
        raise ValueError("validation_days must be positive")

    ordered = _prepare_time_data(
        data,
        timestamp_column=timestamp_column,
    )

    latest_timestamp = ordered[timestamp_column].max()

    # split_training_data uses an exclusive validation_end.
    # Adding one nanosecond ensures the latest observation is included.
    validation_end = latest_timestamp + pd.Timedelta(
        nanoseconds=1
    )
    validation_start = (
        validation_end
        - pd.Timedelta(days=validation_days)
    )

    return split_training_data(
        ordered,
        timestamp_column=timestamp_column,
        validation_start=validation_start,
        validation_end=validation_end,
        lookback_days=lookback_days,
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
    if validation_days <= 0:
        raise ValueError("validation_days must be positive")

    if step_days <= 0:
        raise ValueError("step_days must be positive")

    if folds <= 0:
        raise ValueError("folds must be positive")

    ordered = _prepare_time_data(
        data,
        timestamp_column=timestamp_column,
    )

    validation_duration = pd.Timedelta(
        days=validation_days
    )
    step_duration = pd.Timedelta(days=step_days)

    latest_validation_end = (
        ordered[timestamp_column].max()
        + pd.Timedelta(nanoseconds=1)
    )

    splits: list[TimeSplit] = []

    # Oldest fold first and most recent fold last.
    for fold in reversed(range(folds)):
        validation_end = (
            latest_validation_end
            - step_duration * fold
        )
        validation_start = (
            validation_end
            - validation_duration
        )

        splits.append(
            split_training_data(
                ordered,
                timestamp_column=timestamp_column,
                validation_start=validation_start,
                validation_end=validation_end,
                lookback_days=lookback_days,
            )
        )

    return splits