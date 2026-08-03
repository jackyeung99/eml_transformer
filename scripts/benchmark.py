from __future__ import annotations

import gc
import json
import os
from pathlib import Path
from time import perf_counter
from eml_transformer.sources.registry import create_source, available_sources
from eml_transformer.schema.records import BronzeRecord

import pandas as pd
import psutil
import cProfile
import pstats


ROOT = Path("")

BRONZE_PATH = (
    ROOT
    / "data"
    / "bronze"
    / "source=gdelt"
    / "records.jsonl"
)

SILVER_PATH = (
    ROOT
    / "data"
    / "silver"
    / "source=gdelt"
    / "records.parquet"
)

SAMPLE_SIZE = 500_000

process = psutil.Process(os.getpid())


def profile_standardization(
    bronze_records,
    source,
    sample_size=20_000,
):
    profiler = cProfile.Profile()
    profiler.enable()

    for record in bronze_records[:sample_size]:
        source.standardize_record(record)

    profiler.disable()

    stats = pstats.Stats(profiler)
    stats.strip_dirs()
    stats.sort_stats("cumulative")
    stats.print_stats(30)

def current_memory_gb() -> float:
    return process.memory_info().rss / 1024**3


def print_result(
    stage: str,
    seconds: float,
    rows: int,
    start_memory_gb: float,
) -> None:
    current_gb = current_memory_gb()

    print(
        f"{stage:<25} "
        f"rows={rows:>10,}  "
        f"seconds={seconds:>8.2f}  "
        f"rows/sec={rows / seconds if seconds else 0:>12,.0f}  "
        f"memory={current_gb:>7.2f} GB  "
        f"memory_change={current_gb - start_memory_gb:>+7.2f} GB"
    )


def benchmark_bronze_read() -> list[BronzeRecord]:
    gc.collect()
    start_memory = current_memory_gb()
    start = perf_counter()

    records = []

    with BRONZE_PATH.open("r", encoding="utf-8") as file:
        for index, line in enumerate(file):
            if index >= SAMPLE_SIZE:
                break

            record = BronzeRecord.from_dict(json.loads(line))
            records.append(record)

    print_result(
        stage="Bronze JSONL read",
        seconds=perf_counter() - start,
        rows=len(records),
        start_memory_gb=start_memory,
    )

    return records


def benchmark_standardization(
    bronze_records: list[BronzeRecord],
    source,
) -> pd.DataFrame:
    gc.collect()
    start_memory = current_memory_gb()
    start = perf_counter()

    rows = []
    failures = 0

    for bronze_record in bronze_records:
        try:
            result = source.standardize_record(bronze_record)


            if result is None:
                continue

            standardized_records = (
                result if isinstance(result, list) else [result]
            )

            for record in standardized_records:
                row = record.to_dict()

                # Simulate the proposed silver schema without modifying files.
                row.pop("raw", None)
                rows.append(row)

        except Exception:
            failures += 1

    print_result(
        stage="Standardization",
        seconds=perf_counter() - start,
        rows=len(rows),
        start_memory_gb=start_memory,
    )
    print(f"Standardization failures: {failures:,}")

    gc.collect()
    start_memory = current_memory_gb()
    start = perf_counter()

    dataframe = pd.DataFrame.from_records(rows)

    print_result(
        stage="DataFrame creation",
        seconds=perf_counter() - start,
        rows=len(dataframe),
        start_memory_gb=start_memory,
    )

    dataframe_size = (
        dataframe.memory_usage(index=True, deep=True).sum() / 1024**3
    )
    print(f"DataFrame deep size: {dataframe_size:.2f} GB")

    return dataframe


def benchmark_silver_read() -> pd.DataFrame:
    gc.collect()
    start_memory = current_memory_gb()
    start = perf_counter()

    dataframe = pd.read_parquet(SILVER_PATH)

    print_result(
        stage="Silver Parquet read",
        seconds=perf_counter() - start,
        rows=len(dataframe),
        start_memory_gb=start_memory,
    )

    dataframe_size = (
        dataframe.memory_usage(index=True, deep=True).sum() / 1024**3
    )
    print(f"Silver DataFrame deep size: {dataframe_size:.2f} GB")

    return dataframe


if __name__ == '__main__':
    import eml_transformer.sources.text.iem_afos



    # bronze = benchmark_bronze_read()
    benchmark_silver_read()

  
    # source = create_source(name='gdelt')
    # benchmark_standardization(bronze, source)
    # profile_standardization(bronze, source)

