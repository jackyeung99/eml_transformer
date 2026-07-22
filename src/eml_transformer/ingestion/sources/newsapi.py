from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import requests

from eml_transformer.ingestion.base import TextSource
from eml_transformer.ingestion.registry import register_source
from eml_transformer.ingestion.schema import BronzeRecord, TextRecord
from eml_transformer.utils.dates import parse_utc_datetime, utc_now
from eml_transformer.utils.stamping import stable_hash


logger = logging.getLogger(__name__)


@register_source("newsapi")
class NewsAPISource(TextSource):
    """
    Ingest news articles from NewsAPI.

    Supports incremental ingestion and date-windowed backfills.
    """

    name = "newsapi"
    source_type = "api"
    update_mode = "incremental"
    supports_backfill = True
    default_lookback_days = 3

    def __init__(
        self,
        api_key: str,
        query: str,
        language: str = "en",
        sort_by: str = "relevancy",
        page_size: int = 100,
        max_pages: int = 1,
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key
        self.query = query
        self.language = language
        self.sort_by = sort_by
        self.page_size = page_size
        self.max_pages = max_pages
        self.timeout = timeout

        self.base_url = "https://newsapi.org/v2/everything"

        self.headers = {
            "User-Agent": "eml-transformer-research",
        }

    # ------------------------------------------------------------------
    # Public pipeline interface
    # ------------------------------------------------------------------

    def fetch_records(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[BronzeRecord]:
        """Fetch NewsAPI articles and construct bronze records."""
        raw_response = self._fetch_raw(
            from_date=from_date,
            to_date=to_date,
        )

        return self._build_bronze_records(raw_response)


    def standardize_record(
        self,
        record: BronzeRecord,
    ) -> TextRecord:
        """
        Convert one bronze NewsAPI article into a silver TextRecord.
        """
        article = record.raw
        source_info = article.get("source") or {}

        if not isinstance(source_info, dict):
            source_info = {}

        title = article.get("title")
        description = article.get("description")
        content = article.get("content")

        text = "\n\n".join(
            part.strip()
            for part in [
                title,
                description,
                content,
            ]
            if isinstance(part, str) and part.strip()
        )

        return TextRecord(
            record_id=record.record_id,
            source=record.source,
            source_type=self.source_type,
            title=title,
            text=text,
            published_at=record.published_at,
            retrieved_at=record.retrieved_at,
            url=article.get("url"),
            region=None,
            categories=["news"],
            metadata={
                "news_source": source_info.get("name"),
                "news_source_id": source_info.get("id"),
                "author": article.get("author"),
                "query": self.query,
                "language": self.language,
                "sort_by": self.sort_by,
            },
            raw=article,
        )


    # ------------------------------------------------------------------
    # API access
    # ------------------------------------------------------------------

    def _fetch_raw(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Fetch all configured NewsAPI pages.
        """
        all_articles: list[dict[str, Any]] = []
        total_results: int | None = None

        for page in range(1, self.max_pages + 1):
            raw_page = self._fetch_page(
                page=page,
                from_date=from_date,
                to_date=to_date,
            )

            if raw_page.get("status") != "ok":
                raise RuntimeError(
                    f"NewsAPI request failed: {raw_page}"
                )

            if total_results is None:
                value = raw_page.get("totalResults")

                if isinstance(value, int):
                    total_results = value

            articles = raw_page.get("articles", [])

            if not isinstance(articles, list):
                raise RuntimeError(
                    "NewsAPI response field 'articles' must be a list"
                )

            if not articles:
                break

            all_articles.extend(articles)

            if len(articles) < self.page_size:
                break

            if (
                total_results is not None
                and len(all_articles) >= total_results
            ):
                break

        return {
            "status": "ok",
            "totalResults": total_results or len(all_articles),
            "articles": all_articles,
        }

    def _fetch_page(
        self,
        page: int,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Fetch one NewsAPI page.
        """
        params: dict[str, Any] = {
            "q": self.query,
            "language": self.language,
            "sortBy": self.sort_by,
            "pageSize": self.page_size,
            "page": page,
            "apiKey": self.api_key,
        }

        if from_date is not None:
            params["from"] = from_date.isoformat()

        if to_date is not None:
            params["to"] = to_date.isoformat()

        response = requests.get(
            self.base_url,
            params=params,
            headers=self.headers,
            timeout=self.timeout,
        )

        response.raise_for_status()

        payload = response.json()

        if not isinstance(payload, dict):
            raise RuntimeError(
                "NewsAPI response must be a JSON object"
            )

        return payload

    # ------------------------------------------------------------------
    # Bronze construction
    # ------------------------------------------------------------------
    

    
    def _build_bronze_records(
        self,
        raw_response: dict[str, Any],
    ) -> list[BronzeRecord]:
        """Convert source-native NewsAPI articles into bronze records."""
        articles = raw_response.get("articles", [])

        if not isinstance(articles, list):
            raise ValueError(
                "NewsAPI response field 'articles' must be a list"
            )

        retrieved_at = utc_now()
        records: list[BronzeRecord] = []
        seen_ids: set[str] = set()

        for article in articles:
            if not isinstance(article, dict):
                logger.warning(
                    "Skipping NewsAPI article that is not a dictionary"
                )
                continue

            try:
                record = self._build_bronze_record(
                    article=article,
                    retrieved_at=retrieved_at,
                )
            except (TypeError, ValueError) as exc:
                logger.warning(
                    "Skipping malformed NewsAPI article | error=%s",
                    exc,
                )
                continue

            if record.record_id in seen_ids:
                continue

            seen_ids.add(record.record_id)
            records.append(record)

        return records


    def _build_bronze_record(
        self,
        article: dict[str, Any],
        retrieved_at: datetime,
    ) -> BronzeRecord:
        """Construct one bronze record from a NewsAPI article."""
        url = article.get("url")
        published_at_raw = article.get("publishedAt")

        if not isinstance(url, str) or not url.strip():
            raise ValueError("NewsAPI article is missing its URL")

        if (
            not isinstance(published_at_raw, str)
            or not published_at_raw.strip()
        ):
            raise ValueError(
                f"NewsAPI article {url!r} is missing publishedAt"
            )

        normalized_url = url.strip()
        published_at = parse_utc_datetime(published_at_raw)

        fingerprint = stable_hash(
            {
                "url": normalized_url,
            }
        )

        return BronzeRecord(
            source=self.name,
            record_id=f"{self.name}:{fingerprint}",
            published_at=published_at,
            retrieved_at=retrieved_at,
            raw=article,
        )
    