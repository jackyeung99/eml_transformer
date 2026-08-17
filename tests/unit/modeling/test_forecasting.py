from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from eml_transformer.modeling.forecasting import (
    GeneratedForecast,
    generate_forecast,
)


UTC = timezone.utc

TRAINED_AT = datetime(
    2026,
    1,
    1,
    tzinfo=UTC,
)
GENERATED_AT = datetime(
    2026,
    1,
    10,
    0,
    5,
    tzinfo=UTC,
)


class FakeForecastModel:
    def __init__(
        self,
        *,
        requires_exogenous: bool,
        predictions: list[float],
    ) -> None:
        self.requires_exogenous = requires_exogenous
        self.predictions = predictions
        self.calls: list[dict[str, Any]] = []

    def forecast(
        self,
        *,
        steps: int,
        X: pd.DataFrame | None,
    ) -> list[float]:
        self.calls.append(
            {
                "steps": steps,
                "X": (
                    X.copy(deep=True)
                    if X is not None
                    else None
                ),
            }
        )

        return list(self.predictions)


def make_metadata(
    *,
    features: tuple[str, ...] = (),
    target: str = "actual_load",
) -> SimpleNamespace:
    return SimpleNamespace(
        name="miso_load",
        model_type="ridge",
        model_version="model-v1",
        trained_at=TRAINED_AT,
        features=features,
        target=target,
    )


def make_non_exogenous_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "observed_at": pd.to_datetime(
                [
                    "2026-01-10T00:00:00Z",
                    "2026-01-10T02:00:00Z",
                    "2026-01-10T01:00:00Z",
                ]
            ),
            "actual_load": [
                100.0,
                102.0,
                101.0,
            ],
        }
    )


def make_exogenous_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "observed_at": pd.to_datetime(
                [
                    "2026-01-10T00:00:00Z",
                    "2026-01-10T01:00:00Z",
                    "2026-01-10T02:00:00Z",
                    "2026-01-10T03:00:00Z",
                    "2026-01-10T04:00:00Z",
                ]
            ),
            "actual_load": [
                100.0,
                101.0,
                102.0,
                None,
                None,
            ],
            "hour": [
                0,
                1,
                2,
                3,
                4,
            ],
            "temperature": [
                30.0,
                31.0,
                32.0,
                33.0,
                34.0,
            ],
        }
    )


def test_generate_non_exogenous_forecast():
    model = FakeForecastModel(
        requires_exogenous=False,
        predictions=[
            103.0,
            104.0,
            105.0,
        ],
    )
    metadata = make_metadata()

    result = generate_forecast(
        model,
        metadata,
        make_non_exogenous_data(),
        timestamp_column="observed_at",
        generated_at=GENERATED_AT,
        forecast_steps=3,
        frequency="1h",
    )

    assert isinstance(
        result,
        GeneratedForecast,
    )
    assert result.records_written == 3
    assert result.forecast_origin == datetime(
        2026,
        1,
        10,
        2,
        tzinfo=UTC,
    )
    assert result.generated_at == GENERATED_AT

    records = result.records

    assert records["forecast_for"].tolist() == [
        pd.Timestamp(
            "2026-01-10T03:00:00Z"
        ),
        pd.Timestamp(
            "2026-01-10T04:00:00Z"
        ),
        pd.Timestamp(
            "2026-01-10T05:00:00Z"
        ),
    ]
    assert records["horizon"].tolist() == [
        1,
        2,
        3,
    ]
    assert records["predicted_value"].tolist() == [
        103.0,
        104.0,
        105.0,
    ]

    assert records["model_name"].unique().tolist() == [
        "miso_load"
    ]
    assert records["model_type"].unique().tolist() == [
        "ridge"
    ]
    assert records[
        "model_version"
    ].unique().tolist() == [
        "model-v1"
    ]

    assert model.calls == [
        {
            "steps": 3,
            "X": None,
        }
    ]


def test_generate_exogenous_forecast_uses_future_rows():
    model = FakeForecastModel(
        requires_exogenous=True,
        predictions=[
            103.5,
            104.5,
        ],
    )
    metadata = make_metadata(
        features=(
            "hour",
            "temperature",
        )
    )

    result = generate_forecast(
        model,
        metadata,
        make_exogenous_data(),
        timestamp_column="observed_at",
        generated_at=GENERATED_AT,
        forecast_steps=2,
        frequency="1h",
    )

    assert result.forecast_origin == datetime(
        2026,
        1,
        10,
        2,
        tzinfo=UTC,
    )

    assert result.records[
        "forecast_for"
    ].tolist() == [
        pd.Timestamp(
            "2026-01-10T03:00:00Z"
        ),
        pd.Timestamp(
            "2026-01-10T04:00:00Z"
        ),
    ]

    assert len(model.calls) == 1
    assert model.calls[0]["steps"] == 2

    X_future = model.calls[0]["X"]

    assert X_future is not None
    assert X_future.columns.tolist() == [
        "hour",
        "temperature",
    ]
    assert X_future.to_dict(
        orient="records"
    ) == [
        {
            "hour": 3,
            "temperature": 33.0,
        },
        {
            "hour": 4,
            "temperature": 34.0,
        },
    ]


def test_explicit_forecast_origin_is_used():
    model = FakeForecastModel(
        requires_exogenous=False,
        predictions=[
            101.0,
        ],
    )
    metadata = make_metadata()

    explicit_origin = datetime(
        2026,
        1,
        20,
        tzinfo=UTC,
    )

    result = generate_forecast(
        model,
        metadata,
        make_non_exogenous_data(),
        timestamp_column="observed_at",
        generated_at=GENERATED_AT,
        forecast_steps=1,
        frequency="1D",
        forecast_origin=explicit_origin,
    )

    assert result.forecast_origin == explicit_origin
    assert result.records.loc[
        0,
        "forecast_for",
    ] == pd.Timestamp(
        "2026-01-21T00:00:00Z"
    )


def test_forecast_ids_are_stable():
    model = FakeForecastModel(
        requires_exogenous=False,
        predictions=[
            103.0,
            104.0,
        ],
    )
    metadata = make_metadata()
    data = make_non_exogenous_data()

    first = generate_forecast(
        model,
        metadata,
        data,
        timestamp_column="observed_at",
        generated_at=GENERATED_AT,
        forecast_steps=2,
        frequency="1h",
    )

    second = generate_forecast(
        model,
        metadata,
        data,
        timestamp_column="observed_at",
        generated_at=GENERATED_AT,
        forecast_steps=2,
        frequency="1h",
    )

    assert first.records[
        "forecast_id"
    ].tolist() == second.records[
        "forecast_id"
    ].tolist()

    assert first.records[
        "forecast_id"
    ].is_unique


@pytest.mark.parametrize(
    (
        "data",
        "forecast_steps",
        "timestamp_column",
        "expected_message",
    ),
    [
        (
            pd.DataFrame(),
            1,
            "observed_at",
            "Forecast input is empty",
        ),
        (
            pd.DataFrame(
                {
                    "observed_at": [
                        "2026-01-01T00:00:00Z"
                    ],
                    "actual_load": [100.0],
                }
            ),
            0,
            "observed_at",
            "forecast_steps must be positive",
        ),
        (
            pd.DataFrame(
                {
                    "actual_load": [100.0],
                }
            ),
            1,
            "observed_at",
            "Missing timestamp column",
        ),
    ],
)
def test_rejects_invalid_forecast_input(
    data,
    forecast_steps,
    timestamp_column,
    expected_message,
):
    model = FakeForecastModel(
        requires_exogenous=False,
        predictions=[
            100.0,
        ],
    )

    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        generate_forecast(
            model,
            make_metadata(),
            data,
            timestamp_column=timestamp_column,
            generated_at=GENERATED_AT,
            forecast_steps=forecast_steps,
            frequency="1h",
        )


def test_requires_origin_when_target_is_missing():
    model = FakeForecastModel(
        requires_exogenous=False,
        predictions=[
            100.0,
        ],
    )

    data = pd.DataFrame(
        {
            "observed_at": [
                "2026-01-01T00:00:00Z",
            ]
        }
    )

    with pytest.raises(
        ValueError,
        match="forecast_origin must be provided",
    ):
        generate_forecast(
            model,
            make_metadata(),
            data,
            timestamp_column="observed_at",
            generated_at=GENERATED_AT,
            forecast_steps=1,
            frequency="1h",
        )


def test_rejects_missing_exogenous_features():
    model = FakeForecastModel(
        requires_exogenous=True,
        predictions=[
            103.0,
        ],
    )
    metadata = make_metadata(
        features=(
            "hour",
            "temperature",
        )
    )

    data = make_exogenous_data().drop(
        columns=["temperature"]
    )

    with pytest.raises(
        ValueError,
        match="missing exogenous features",
    ):
        generate_forecast(
            model,
            metadata,
            data,
            timestamp_column="observed_at",
            generated_at=GENERATED_AT,
            forecast_steps=1,
            frequency="1h",
        )


def test_rejects_insufficient_future_exogenous_rows():
    model = FakeForecastModel(
        requires_exogenous=True,
        predictions=[
            103.0,
            104.0,
            105.0,
        ],
    )
    metadata = make_metadata(
        features=(
            "hour",
            "temperature",
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "Not enough future exogenous rows"
        ),
    ):
        generate_forecast(
            model,
            metadata,
            make_exogenous_data(),
            timestamp_column="observed_at",
            generated_at=GENERATED_AT,
            forecast_steps=3,
            frequency="1h",
        )


def test_rejects_missing_future_exogenous_values():
    model = FakeForecastModel(
        requires_exogenous=True,
        predictions=[
            103.0,
            104.0,
        ],
    )
    metadata = make_metadata(
        features=(
            "hour",
            "temperature",
        )
    )

    data = make_exogenous_data()
    data.loc[
        data["observed_at"]
        == pd.Timestamp("2026-01-10T03:00:00Z"),
        "temperature",
    ] = None

    with pytest.raises(
        ValueError,
        match=(
            "Future exogenous features contain "
            "missing values"
        ),
    ):
        generate_forecast(
            model,
            metadata,
            data,
            timestamp_column="observed_at",
            generated_at=GENERATED_AT,
            forecast_steps=2,
            frequency="1h",
        )


def test_rejects_unexpected_prediction_count():
    model = FakeForecastModel(
        requires_exogenous=False,
        predictions=[
            103.0,
        ],
    )

    with pytest.raises(
        ValueError,
        match=(
            "unexpected number of predictions"
        ),
    ):
        generate_forecast(
            model,
            make_metadata(),
            make_non_exogenous_data(),
            timestamp_column="observed_at",
            generated_at=GENERATED_AT,
            forecast_steps=2,
            frequency="1h",
        )


def test_rejects_invalid_frequency():
    model = FakeForecastModel(
        requires_exogenous=False,
        predictions=[
            103.0,
        ],
    )

    with pytest.raises(
        ValueError,
        match="Invalid forecast frequency",
    ):
        generate_forecast(
            model,
            make_metadata(),
            make_non_exogenous_data(),
            timestamp_column="observed_at",
            generated_at=GENERATED_AT,
            forecast_steps=1,
            frequency="not-a-frequency",
        )