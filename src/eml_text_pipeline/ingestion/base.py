from abc import ABC, abstractmethod
from typing import Any
import pandas as pd


class TextSource(ABC):
    """
    Abstract base class for textual data sources.

    A TextSource is responsible for:
        1. Retrieving raw source data
        2. Parsing raw data into standardized records
        3. Returning a normalized dataframe schema
    """

    name: str
    source_type: str

    REQUIRED_COLUMNS = [
        "source",
        "source_type",
        "title",
        "published_at",
        "retrieved_at",
        "url",
        "raw_text",
        "clean_text",
    ]

    @abstractmethod
    def fetch_raw(self) -> Any:
        """
        Retrieve raw source payload.

        Examples:
            - API JSON
            - RSS XML
            - HTML
            - PDF text
        """
        pass

    @abstractmethod
    def parse_records(self, raw: Any) -> pd.DataFrame:
        """
        Convert raw payload into standardized records.

        Returns:
            pd.DataFrame following REQUIRED_COLUMNS schema.
        """
        pass

    def validate_schema(self, df: pd.DataFrame) -> None:
        """
        Validate required columns exist.
        """
        missing = [
            col for col in self.REQUIRED_COLUMNS
            if col not in df.columns
        ]

        if missing:
            raise ValueError(
                f"{self.name} missing required columns: {missing}"
            )

    def run(self) -> pd.DataFrame:
        """
        Execute full ingestion workflow.
        """
        raw = self.fetch_raw()
        df = self.parse_records(raw)

        self.validate_schema(df)

        return df