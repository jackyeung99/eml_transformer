from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from eml_transformer.ingestion.schema import (
    TextRecord,
    TEXT_RECORD_COLUMNS,
)

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

    



    
