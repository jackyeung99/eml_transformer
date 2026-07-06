from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import aiohttp
from matplotlib.pylab import record
import pandas as pd
from tqdm.auto import tqdm

import eml_transformer.ingestion.sources  # noqa: F401
from eml_transformer.extraction.scraper import (
    ArticleScraperConfig,
    HybridArticleScraper,
)
from eml_transformer.ingestion.registry import create_source
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.storage import Storage
from eml_transformer.text_processing.cleaning import clean_text

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
            "read": self.records_read,
            "out": self.records_out,
            "failed": self.records_failed,
            "input": self.input_key,
            "output": self.output_key,
            "error": self.error,
        }


class ScrapingPipeline:
    DEFAULT_INPUT_ARTIFACT = "records"
    DEFAULT_OUTPUT_ARTIFACT = "extracted_articles"

    def __init__(
        self,
        storage: Storage,
        paths: StoragePaths,
        scraper: HybridArticleScraper | None = None
    ) -> None:
        self.storage = storage
        self.paths = paths
        self.scraper = scraper

    def run_all(
        self,
        source_configs: dict[str, dict],
    ) -> list[ScrapingResult]:
        logger.info("Starting scraping for %s sources", len(source_configs))

        results: list[ScrapingResult] = []

        for source_name, source_kwargs in source_configs.items():
            if not source_kwargs.get("enabled", True):
                continue

            scraping_config = source_kwargs.get("scraping", {})

            if not scraping_config.get("enabled", False):
                continue

            results.append(
                self.run_source(
                    source_name=source_name,
                    source_config=source_kwargs,
                )
            )

        logger.info("Scraping complete")

        return results

    def run_source(
        self,
        source_name: str,
        source_config: dict[str, Any],
    ) -> ScrapingResult:
        scraping_config = source_config.get("scraping", {})

        input_artifact = scraping_config.get(
            "input",
            self.DEFAULT_INPUT_ARTIFACT,
        )

        output_artifact = scraping_config.get(
            "output",
            self.DEFAULT_OUTPUT_ARTIFACT,
        )

        input_key: str | None = None
        output_key: str | None = None

        try:
            source = create_source(
                source_name,
                **source_config.get("ingestion", {}),
            )

            input_key = self.paths.silver_records(
                source=source.name,
                name=input_artifact,
            )

            output_key = self.paths.silver_records(
                source=source.name,
                name=output_artifact,
            )

            logger.info(
                "Starting scraping | source=%s | input=%s | output=%s",
                source.name,
                input_key,
                output_key,
            )

            if not self.storage.exists(input_key):
                return ScrapingResult(
                    status="skipped",
                    source=source.name,
                    input_artifact=input_artifact,
                    output_artifact=output_artifact,
                    records_read=0,
                    records_out=0,
                    input_key=input_key,
                    output_key=output_key,
                    error=f"No scraping input found: {input_key}",
                )

            input_df = self.storage.read_parquet(input_key)

            if input_df.empty:
                return ScrapingResult(
                    status="skipped",
                    source=source.name,
                    input_artifact=input_artifact,
                    output_artifact=output_artifact,
                    records_read=0,
                    records_out=0,
                    input_key=input_key,
                    output_key=output_key,
                    records=input_df,
                    error="Scraping input is empty",
                )

            existing_df = self._load_existing_output(output_key)

            to_scrape_df = self._select_records_to_scrape(
                input_df=input_df,
                existing_df=existing_df,
                retry_failed=scraping_config.get("retry_failed", True),
            )

            if to_scrape_df.empty:
                return ScrapingResult(
                    status="up_to_date",
                    source=source.name,
                    input_artifact=input_artifact,
                    output_artifact=output_artifact,
                    records_read=len(input_df),
                    records_out=len(existing_df),
                    records_failed=self._count_failed(existing_df),
                    input_key=input_key,
                    output_key=output_key,
                    records=existing_df,
                )

            batch_size = scraping_config.get("batch_size", 100)

            total_failed = 0
            total_scraped = 0
            final_df = existing_df

            logging.getLogger("trafilatura").setLevel(logging.ERROR)
            logging.getLogger("trafilatura.metadata").setLevel(logging.ERROR)

            with tqdm(
                total=len(to_scrape_df),
                desc=f"Scraping {source.name}",
                unit="url",
                dynamic_ncols=True,
            ) as pbar:
                for batch_start in range(0, len(to_scrape_df), batch_size):
                    batch_df = to_scrape_df.iloc[
                        batch_start : batch_start + batch_size
                    ]

                    scraped_batch_df = asyncio.run(
                        self._scrape_dataframe_async(
                            df=batch_df,
                            scraping_config=scraping_config,
                        )
                    )

                    final_df = self._merge_scraped_results(
                        existing_df=final_df,
                        scraped_df=scraped_batch_df,
                    )

                    self.storage.write_parquet(final_df, output_key)

                    batch_failed = self._count_failed(scraped_batch_df)

                    total_failed += batch_failed
                    total_scraped += len(scraped_batch_df)

                    pbar.set_postfix(
                        scraped=total_scraped,
                        failed=total_failed,
                        total=len(final_df),
                    )
                    pbar.update(len(batch_df))

            logger.info(
                "Scraping complete | source=%s | read=%s | scraped=%s | failed=%s | total=%s | output=%s",
                source.name,
                len(input_df),
                total_scraped,
                total_failed,
                len(final_df),
                output_key,
            )

            return ScrapingResult(
                status="success",
                source=source.name,
                input_artifact=input_artifact,
                output_artifact=output_artifact,
                records_read=len(input_df),
                records_out=len(final_df),
                records_failed=total_failed,
                input_key=input_key,
                output_key=output_key,
                records=final_df,
            )

        except Exception as exc:
            logger.exception("Scraping failed | source=%s", source_name)

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

    async def _scrape_dataframe_async(
        self,
        df: pd.DataFrame,
        scraping_config: dict[str, Any],
    ) -> pd.DataFrame:
        scraper = self.scraper or HybridArticleScraper(
                ArticleScraperConfig(
                    request_timeout=scraping_config.get("request_timeout", 15),
                    playwright_timeout=scraping_config.get("playwright_timeout", 30_000),
                    fallback_on_forbidden=scraping_config.get(
                        "fallback_on_forbidden",
                        True,
                    ),
                )
            )

        semaphore = asyncio.Semaphore(
            scraping_config.get("max_concurrency", 10)
        )

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
                            "title": None,
                            "text": "",
                            "text_length": 0,
                            "metadata": {
                                **self._coerce_metadata(record_dict.get("metadata")),
                                "scraping": {
                                    "status": "failed",
                                    "success": False,
                                    "status_code": None,
                                    "error_type": "pipeline_exception",
                                    "error_message": str(exc),
                                    "fetch_method": None,
                                    "fallback_used": False,
                                    "extractor": None,
                                    "author": None,
                                    "trafilatura_date": None,
                                    "retrieved_at": None,
                                    "attempt_count": 0,
                                },
                            },
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
        original_metadata = self._coerce_metadata(
            record_dict.get("metadata")
        )
        scraped_metadata = self._coerce_metadata(
            scrape_result.get("metadata")
        )

        original_published_at = record_dict.get("published_at")
        scraped_published_at = scrape_result.get("published_at")

        if scraped_published_at:
            final_published_at = scraped_published_at
            published_at_metadata = {
                "source": "page_metadata",
                "precision": "second",
            }
        else:
            final_published_at = original_published_at
            published_at_metadata = {
                "source": "gdelt",
                "precision": "15min",
            }

        metadata = {
            **original_metadata,
            **scraped_metadata,
            "published_at": published_at_metadata,
        }

        return {
            **record_dict,
            **scrape_result,
            "published_at": final_published_at,
            "metadata": metadata,
        }

    def _clean_scraped_record(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        record["title"] = record.get("title") or ""
        record["text"] = record.get("text") or ""
        record["metadata"] = self._coerce_metadata(record.get("metadata"))

        scrape_status = self._get_scraping_status(record["metadata"])

        if scrape_status == "success":
            record["title"] = clean_text(record["title"])
            record["text"] = clean_text(record["text"])

        record["text_length"] = len(record["text"])

        return record

    def _load_existing_output(self, output_key: str) -> pd.DataFrame:
        if not self.storage.exists(output_key):
            return pd.DataFrame()

        return self.storage.read_parquet(output_key)

    def _select_records_to_scrape(
        self,
        input_df: pd.DataFrame,
        existing_df: pd.DataFrame,
        retry_failed: bool,
    ) -> pd.DataFrame:
        if "record_id" not in input_df.columns:
            raise ValueError("Scraping input must contain a 'record_id' column.")

        if "url" not in input_df.columns:
            raise ValueError("Scraping input must contain a 'url' column.")

        input_df = input_df.drop_duplicates(
            subset=["record_id"],
            keep="last",
        ).copy()

        if existing_df.empty or "record_id" not in existing_df.columns:
            return input_df

        existing_df = existing_df.copy()

        existing_df["scraping_status"] = existing_df["metadata"].map(
            self._get_scraping_status
        )

        if retry_failed:
            processed_df = existing_df[
                existing_df["scraping_status"].isin(NON_RETRYABLE_STATUSES)
            ]
        else:
            processed_df = existing_df

        processed_record_ids = set(
            processed_df["record_id"].dropna()
        )

        return input_df.loc[
            ~input_df["record_id"].isin(processed_record_ids)
        ].copy()
    
    def _get_scraping_status(self, metadata: Any) -> str | None:
        metadata = self._coerce_metadata(metadata)
        scraping = self._coerce_metadata(metadata.get("scraping"))

        return scraping.get("status")

    def _merge_scraped_results(
        self,
        existing_df: pd.DataFrame,
        scraped_df: pd.DataFrame,
    ) -> pd.DataFrame:
        if existing_df.empty:
            return scraped_df.reset_index(drop=True)

        if scraped_df.empty:
            return existing_df.reset_index(drop=True)

        final_df = pd.concat(
            [existing_df, scraped_df],
            ignore_index=True,
        )

        return (
            final_df
            .drop_duplicates(subset=["record_id"], keep="last")
            .reset_index(drop=True)
        )

    def _count_failed(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0

        if "metadata" not in df.columns:
            return len(df)

        statuses = df["metadata"].map(self._get_scraping_status)

        return int(statuses.ne("success").sum())

    def _coerce_metadata(self, metadata: Any) -> dict[str, Any]:
        if metadata is None:
            return {}

        if isinstance(metadata, dict):
            return metadata

        return {"metadata": metadata}