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

def expand_dimensions(
    df: pd.DataFrame,
    *,
    column: str = "dimensions",
    prefix: str = "",
    drop: bool = True,
) -> pd.DataFrame:
    """
    Expand a dictionary-valued dimensions column into regular columns.

    Example:
        dimensions={"from_region": "MISO", "to_region": "PJM"}

    becomes:
        from_region="MISO"
        to_region="PJM"
    """
    if column not in df.columns:
        raise KeyError(f"Missing dimensions column: {column!r}")

    result = df.copy()

    dimensions = result[column].map(
        lambda value: value if isinstance(value, dict) else {}
    )

    expanded = pd.json_normalize(dimensions)

    if prefix:
        expanded = expanded.add_prefix(prefix)

    conflicts = set(expanded.columns).intersection(result.columns)

    if conflicts:
        conflict_names = ", ".join(sorted(conflicts))
        raise ValueError(
            "Expanded dimension columns conflict with existing columns: "
            f"{conflict_names}. Provide a prefix to avoid conflicts."
        )

    expanded.index = result.index
    result = pd.concat([result, expanded], axis=1)

    if drop:
        result = result.drop(columns=column)

    return result