from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

from eml_text_pipeline.ingestion.base import TextSource


class NewsAPISource(TextSource):
    """
    Ingest news articles from NewsAPI.
    """

    name = "newsapi"
    source_type = "api"

    def __init__(
        self,
        api_key: str,
        query: str,
        language: str = "en",
        sort_by: str = "relevancy",
        page_size: int = 100,
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.query = query
        self.language = language
        self.page_size = page_size
        self.timeout = timeout
        self.sort_by = sort_by

        self.base_url = (
            "https://newsapi.org/v2/everything"
        )

        self.headers = {
            "User-Agent": "Mozilla/5.0",
        }

    def fetch_raw(self) -> Any:
        """
        Fetch raw NewsAPI response.
        """
        params = {
            "q": self.query,
            "language": self.language,
            "pageSize": self.page_size,
            "sortBy": self.sort_by,
            "apiKey": self.api_key,
        }

        response = requests.get(
            self.base_url,
            params=params,
            headers=self.headers,
            timeout=self.timeout,
        )

        response.raise_for_status()

        return response.json()

    def parse_records(self, raw: Any) -> pd.DataFrame:
        """
        Parse NewsAPI response into standardized records.
        """
        records = []

        retrieved_at = datetime.now(
            timezone.utc
        ).isoformat()

        articles = raw.get("articles", [])

        for article in articles:

            source_info = article.get("source", {})

            title = article.get("title")
            description = article.get("description")
            content = article.get("content")
            published_at = article.get("publishedAt")
            url = article.get("url")

            source_name = source_info.get("name")

            clean_text = "\n".join(
                filter(
                    None,
                    [
                        title,
                        description,
                        content,
                    ],
                )
            )

            raw_text = {
                "title": title,
                "description": description,
                "content": content,
            }

            record = {
                "source": self.name,
                "source_type": self.source_type,
                "title": title,
                "published_at": published_at,
                "retrieved_at": retrieved_at,
                "url": url,
                "raw_text": str(raw_text),
                "clean_text": clean_text,
                "metadata": {
                    "news_source": source_name,
                    "author": article.get("author"),
                },
            }

            records.append(record)

        return pd.DataFrame(records)