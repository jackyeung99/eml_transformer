# scripts/backfill_newsapi.py

from __future__ import annotations

import argparse
import copy
import os
from datetime import date, timedelta

from dotenv import load_dotenv

from eml_transformer.logging import setup_logging
from eml_transformer.pipelines.ingestion_pipeline import IngestionPipeline
from eml_transformer.runtime import build_runtime


NEWS_QUERY = """
(
    "Midcontinent Independent System Operator"
    OR ERCOT
    OR PJM
)
AND
(
    electricity
    OR grid
    OR "power market"
    OR transmission
)
"""


def iter_date_windows(start: date, end: date, window_days: int):
    current = start

    while current <= end:
        window_end = min(
            current + timedelta(days=window_days - 1),
            end,
        )

        yield current.isoformat(), window_end.isoformat()

        current = window_end + timedelta(days=1)


def main():
    load_dotenv()
    setup_logging()

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/dev.yaml")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--page-size", type=int, default=100)

    args = parser.parse_args()

    rt = build_runtime(args.config)

    pipeline = IngestionPipeline(
        storage=rt.storage,
        paths=rt.paths,
    )

    base_source_config = copy.deepcopy(rt.source_configs["newsapi"])

    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end)

    all_results = []

    for from_date, to_date in iter_date_windows(
        start=start_date,
        end=end_date,
        window_days=args.window_days,
    ):
        source_config = copy.deepcopy(base_source_config)

        source_config.update(
            {
                # "enabled": True,
                "api_key": os.environ["NEWSAPI_KEY"],
                "query": NEWS_QUERY,
                "language": "en",
                "page_size": args.page_size,
                "max_pages": args.max_pages,
                "from_date": from_date,
                "to_date": to_date,
                "sort_by": "publishedAt",
            }
        )

        result = pipeline.run_source(
            source_name="newsapi",
            source_kwargs=source_config,
        )

        all_results.append(result)
        print(result)

    return all_results


if __name__ == "__main__":


    '''
    To run use this command
    python scripts/backfill_newsapi.py   --start 2026-04-19   --end 2026-05-20   --window-days 7   --max-pages 1
    '''
    main()