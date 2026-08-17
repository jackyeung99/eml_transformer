"""Read a selected dataset and print pandas memory usage."""

import argparse
import resource
import time
from pathlib import Path

import pandas as pd


# Edit paths and columns here manually.
DATASETS = {
    "gdelt": Path("data/silver/source=gdelt/records.parquet"),
    "iem_afos": Path("data/silver/source=iem_afos/records.parquet"),
}

COLUMNS = [
    "record_id",
    "source",
    "source_type",
    "title",
    "text",
    "published_at",
    "retrieved_at",
    "url",
    "region",
    "categories",
    "metadata",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=DATASETS)
    dataset = parser.parse_args().dataset

    data_path = DATASETS[dataset]

    start = time.perf_counter()

    df = pd.read_parquet(
        data_path,
        columns=COLUMNS,
        dtype_backend="pyarrow",
    )

    elapsed = time.perf_counter() - start
    column_mb = (
        df.memory_usage(index=False, deep=True)
        .div(1024**2)
        .sort_values(ascending=False)
        .rename("MB")
    )
    dataframe_gb = df.memory_usage(index=True, deep=True).sum() / 1024**3
    peak_gb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**2

    print(f"Dataset: {dataset}")
    print(f"Path: {data_path}")
    print(f"Rows: {len(df):,}")
    print(f"Runtime: {elapsed:.2f} seconds")
    print(f"DataFrame memory: {dataframe_gb:.2f} GB")
    print(f"Peak process memory: {peak_gb:.2f} GB")
    print("\nMemory by column:")
    print(column_mb.to_string())
    print("\nDtypes:")
    print(df.dtypes)


if __name__ == "__main__":
    main()