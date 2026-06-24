from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import aiohttp
import pandas as pd
import json 

from eml_transformer.extraction.scraper import (
    ArticleScraperConfig,
    HybridArticleScraper,
)

logger = logging.getLogger(__name__)

NON_RETRYABLE_STATUSES = {
    "success",
    "forbidden",
    "not_found",
}


@dataclass
class ScrapingResult:
    status: str
    source: str

    input_artifact: str
    output_artifact: str

    records_read: int
    records_out: int
    records_failed: int = 0

    input_key: str | None = None
    output_key: str | None = None

    error: str | None = None
    records: pd.DataFrame | None = None

    def to_summary(self) -> dict[str, object]:
        return {
            "source": self.source,
            "status": self.status,
            "input_artifact": self.input_artifact,
            "output_artifact": self.output_artifact,
            "records_read": self.records_read,
            "records_out": self.records_out,
            "records_failed": self.records_failed,
            "input_key": self.input_key,
            "output_key": self.output_key,
            "error": self.error,
        }


class ScrapingPipeline:
    def __init__(
        self,
        storage,
        paths,
        max_concurrency: int = 10,
        retry_failed: bool = True,
        scraper_config: ArticleScraperConfig | None = None,
    ) -> None:
        self.storage = storage
        self.paths = paths
        self.max_concurrency = max_concurrency
        self.retry_failed = retry_failed
        self.scraper_config = scraper_config or ArticleScraperConfig()

    def run_one(self, source_config: dict[str, Any]) -> ScrapingResult:
        source_name = source_config["name"]

        input_artifact = source_config.get("scrape_input_artifact", "records")
        output_artifact = source_config.get(
            "scrape_output_artifact",
            "extracted_articles",
        )

        input_key = self.paths.silver_records(
            source=source_name,
            name=input_artifact,
        )

        output_key = self.paths.silver_records(
            source=source_name,
            name=output_artifact,
        )

        try:
            existing_df = self._load_existing_output(output_key)

            input_df = self.storage.read_parquet(input_key)

            if input_df.empty:
                return ScrapingResult(
                    status="success",
                    source=source_name,
                    input_artifact=input_artifact,
                    output_artifact=output_artifact,
                    records_read=0,
                    records_out=0,
                    records_failed=0,
                    input_key=input_key,
                    output_key=output_key,
                    records=input_df,
                )

            scrape_df = self._select_records_to_scrape(
                input_df=input_df,
                existing_df=existing_df,
            )

            if scrape_df.empty:
                return ScrapingResult(
                    status="skipped",
                    source=source_name,
                    input_artifact=input_artifact,
                    output_artifact=output_artifact,
                    records_read=len(input_df),
                    records_out=len(existing_df),
                    records_failed=self._count_failed(existing_df),
                    input_key=input_key,
                    output_key=output_key,
                    records=existing_df,
                )

            scraped_df = asyncio.run(self._scrape_dataframe(scrape_df))

            output_df = self._merge_scraped_results(
                existing_df=existing_df,
                scraped_df=scraped_df,
            )

            self.storage.write_parquet(output_df, output_key)

            return ScrapingResult(
                status="success",
                source=source_name,
                input_artifact=input_artifact,
                output_artifact=output_artifact,
                records_read=len(input_df),
                records_out=len(output_df),
                records_failed=self._count_failed(output_df),
                input_key=input_key,
                output_key=output_key,
                records=output_df,
            )

        except Exception as exc:
            logger.exception(
                "Scraping failed | source=%s",
                source_name,
            )

            return ScrapingResult(
                status="failed",
                source=source_name,
                input_artifact=input_artifact,
                output_artifact=output_artifact,
                records_read=0,
                records_out=0,
                records_failed=0,
                input_key=input_key,
                output_key=output_key,
                error=str(exc),
            )

    async def _scrape_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        semaphore = asyncio.Semaphore(self.max_concurrency)
        scraper = HybridArticleScraper(self.scraper_config)

        async def scrape_one(
            session: aiohttp.ClientSession,
            record: pd.Series,
        ) -> dict[str, Any]:
            record_dict = record.to_dict()

            async with semaphore:
                try:
                    result = await scraper.scrape(
                        session=session,
                        url=record_dict["url"],
                    )

                    row = self._merge_record_and_scrape_result(
                        record_dict=record_dict,
                        scrape_result=result,
                    )

                    return self._clean_scraped_record(row)

                except Exception as exc:
                    logger.exception(
                        "Record scrape failed | record_id=%s | url=%s",
                        record_dict.get("record_id"),
                        record_dict.get("url"),
                    )

                    return self._clean_scraped_record(
                        {
                            **record_dict,
                            "success": False,
                            "scrape_status": "failed",
                            "error_type": "pipeline_exception",
                            "error_message": str(exc),
                            "text": "",
                            "text_length": 0,
                        }
                    )

        async with aiohttp.ClientSession() as session:
            tasks = [
                scrape_one(session, record)
                for _, record in df.iterrows()
            ]

            rows = await asyncio.gather(*tasks)

        return pd.DataFrame(rows)

    def _merge_record_and_scrape_result(
        self,
        record_dict: dict[str, Any],
        scrape_result: dict[str, Any],
    ) -> dict[str, Any]:
        original_metadata = record_dict.get("metadata") or {}
        scraped_metadata = scrape_result.get("metadata") or {}

        original_published_at = record_dict.get("published_at")
        scraped_published_at = scrape_result.get("published_at")

        published_at = scraped_published_at or original_published_at

        published_at_source = scraped_metadata.get("published_at_source")
        if not published_at_source and original_published_at:
            published_at_source = "source_record"

        metadata = {
            **original_metadata,
            **scraped_metadata,
            "original_published_at": original_published_at,
            "scraped_published_at": scraped_published_at,
            "final_published_at": published_at,
            "published_at_source": published_at_source,
            "has_precise_published_at": bool(published_at),
        }

        return {
            **record_dict,
            **scrape_result,
            "published_at": published_at,
            "metadata": metadata,
        }

    def _select_records_to_scrape(
        self,
        input_df: pd.DataFrame,
        existing_df: pd.DataFrame,
    ) -> pd.DataFrame:
        if existing_df.empty:
            return input_df

        if "record_id" not in input_df.columns:
            raise ValueError("input_df must contain record_id")

        if "record_id" not in existing_df.columns:
            return input_df

        existing = existing_df.copy()

        if not self.retry_failed:
            completed_ids = set(existing["record_id"].dropna())
        else:
            non_retryable = existing[
                existing["scrape_status"].isin(NON_RETRYABLE_STATUSES)
            ]
            completed_ids = set(non_retryable["record_id"].dropna())

        return input_df[
            ~input_df["record_id"].isin(completed_ids)
        ].copy()

    def _merge_scraped_results(
        self,
        existing_df: pd.DataFrame,
        scraped_df: pd.DataFrame,
    ) -> pd.DataFrame:
        if existing_df.empty:
            return scraped_df

        if scraped_df.empty:
            return existing_df

        existing_keep = existing_df[
            ~existing_df["record_id"].isin(scraped_df["record_id"])
        ]

        return pd.concat(
            [existing_keep, scraped_df],
            ignore_index=True,
        )

    def _load_existing_output(self, output_key: str) -> pd.DataFrame:
        if not self.storage.exists(output_key):
            return pd.DataFrame()

        return self.storage.read_parquet(output_key)

    def _clean_scraped_record(
        self,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        metadata = row.get("metadata")

        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {"raw_metadata": metadata}

        if metadata is None:
            metadata = {}

        row["metadata"] = metadata

        if row.get("text") is None:
            row["text"] = ""

        row["text_length"] = len(row.get("text") or "")

        return row

    def _count_failed(self, df: pd.DataFrame) -> int:
        if df.empty or "success" not in df.columns:
            return 0

        return int((~df["success"].fillna(False)).sum())