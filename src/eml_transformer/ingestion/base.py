from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from eml_transformer.ingestion.schema import (
    TextRecord,
    TEXT_RECORD_COLUMNS,
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

    @abstractmethod
    def native_id(self, raw_record: dict[str, Any]) -> str | None:
        '''
        The source's own stable identifier for this raw record.
        Return None if the source does not publish one
        '''
        pass

    def hash_payload(self, raw_record: dict[str, Any]) -> dict[str, Any]:
        '''
        The data hashed when native_id() returns None.
        Override to narrow this to fields that are actually stable
        '''
        return raw_record
    
    def unique_id(self, raw_record: dict[str, Any]) -> str:
        '''
        Stable identity for a raw record. Sources override native_id()
        '''
        native = self.native_id(raw_record)

        if native:
            return f"{self.name}:{native}"
        
        return f"{self.name}: {stable_hash(self.hash_payload(raw_record))}"
    





    
