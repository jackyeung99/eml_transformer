from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from eml_transformer.ingestion.schema import (
    TextRecord,
    TEXT_RECORD_COLUMNS,
    BronzeRecord
)
from eml_transformer.utils.stamping import stable_hash

import hashlib

class TextSource(ABC):
    """
    Base class for textual ingestion sources.
    """
    name: str
    source_type: str


    @abstractmethod
    def fetch_records(self) -> Any:
        '''
        Retrieve raw records with light pre processing and store in bronze/
        '''
        pass

    @abstractmethod
    def standardize_record(self, record: dict[str, Any]) -> TextRecord:
        '''
        format raw records into standardized Textrecord data class store in silver/
        '''
        pass
    

    @staticmethod
    def _deduplicate_records(
        records: list[BronzeRecord],
    ) -> list[BronzeRecord]:
        """Keep the first record for each source ID."""
        unique_records: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for record in records:
            source_id = str(record.record_id)

            if source_id in seen_ids:
                continue

            seen_ids.add(source_id)
            unique_records.append(record)

        return unique_records




    
