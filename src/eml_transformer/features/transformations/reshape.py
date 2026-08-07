from collections.abc import Sequence

import pandas as pd


def long_to_wide(
    frame: pd.DataFrame,
    *,
    index_columns: Sequence[str],
    variable_column: str = "variable",
    value_column: str = "value",
) -> pd.DataFrame:
    keys = [*index_columns, variable_column]

    if frame.duplicated(keys).any():
        raise ValueError(
            f"Cannot pivot because duplicate rows exist for {keys}"
        )

    return (
        frame.pivot(
            index=list(index_columns),
            columns=variable_column,
            values=value_column,
        )
        .reset_index()
        .rename_axis(columns=None)
    )