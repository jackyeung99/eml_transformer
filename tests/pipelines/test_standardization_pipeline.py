import pytest
import pandas as pd
from eml_transformer.pipelines.standardization_pipeline import StandardizationResult
from datetime import datetime
from unittest.mock import MagicMock, patch
from eml_transformer.ingestion.schema import TextRecord
from eml_transformer.pipelines.standardization_pipeline import StandardizationPipeline


class TestStandardizationResultCreation:
    """Test that StandardizationResult can be instantiated correctly"""

    def test_create_with_required_fields(self):
        result = StandardizationResult(
            status="success",
            source="gdelt",
            records_read=90,
            records_out=75
        )
        assert result.status == "success"
        assert result.source == "gdelt"
        assert result.records_read == 90
        assert result.records_out == 75
    
    def test_default_values(self):
        result = StandardizationResult(
            status="success",
            source="gdelt",
            records_read=90,
            records_out=75
        )
        assert result.records_failed == 0
        assert result.bronze_key == None
        assert result.silver_key == None
        assert result.error == None
        assert result.records == None
    
    def test_create_with_all_fields(self):
        df = pd.DataFrame({"text": ["article1", "article2"]})
        result = StandardizationResult(
            status="success",
            source="gdelt",
            records_read=90,
            records_out=75,
            records_failed=15,
            bronze_key="bronze/gdelt/2026-01-01.parquet",
            silver_key="silver/gdelt/2026-01-01.parquet",
            error=None,
            records=df
        )
        assert result.records_failed == 15
        assert result.bronze_key == "bronze/gdelt/2026-01-01.parquet"
        assert result.silver_key == "silver/gdelt/2026-01-01.parquet"
        assert len(result.records) == 2
    
    def test_create_with_error(self):
        result = StandardizationResult(
            status="error",
            source="gdelt",
            records_read=0,
            records_out=0,
            error="409 Request Error"
        )
        assert result.status == "error"
        assert result.error == "409 Request Error"

class TestStandardizationResultToSummary:
    """Test the to_summary method"""

    def test_to_summary_returns_correct_keys(self):
        result = StandardizationResult(
            status="success",
            source="gdelt",
            records_read=90,
            records_out=75
        )
        summary = result.to_summary()
        expected_keys = {"source", "status", "read","out","failed","silver","error"}
        assert set(summary.keys()) == expected_keys
    
    def test_to_summary_values(self):
        result = StandardizationResult(
            status="success",
            source="gdelt",
            records_read=90,
            records_out=75,
            records_failed=15,
            silver_key="silver/gdelt/2026-01-01.parquet"
        )
        summary = result.to_summary()
        assert summary["status"] == "success"
        assert summary["source"] == "gdelt"
        assert summary["read"] == 90
        assert summary["out"] == 75
        assert summary["failed"] == 15
        assert summary["silver"] == "silver/gdelt/2026-01-01.parquet"
        assert summary["error"] is None
    
    def test_to_summary_excludes_records_dataframe(self):
        """to_summary should not include the full DataFrame"""
        df = pd.DataFrame({"text": ["article1"]})
        result = StandardizationResult(
            status="success",
            source="gdelt",
            records_read=1,
            records_out=1,
            records=df
        )
        summary = result.to_summary()
        assert "records" not in summary

class TestCleanRecord:
    """Test the _clean_record helper method"""

    def test_cleans_title_and_text(self, storage, paths):
        pipeline = StandardizationPipeline(storage=storage, paths=paths)
        now = datetime.now()
        record = TextRecord(
            record_id="test-001",
            source="gdelt",
            source_type="news",
            published_at=now,
            retrieved_at=now,
            title="<p>Messy    Title</p>",
            text="<div>Messy   Text</div>"
        )
        cleaned = pipeline._clean_record(record)
        assert cleaned.title == "Messy Title"
        assert cleaned.text == "Messy Text"
    
    def test_handles_none_title(self, storage, paths):
        pipeline = StandardizationPipeline(paths=paths, storage=storage)
        now = datetime.now()
        record = TextRecord(
            record_id="test-002",
            source="gdelt",
            source_type="news",
            published_at=now,
            retrieved_at=now,
            title= None,
            text= "Sample text"
        )
        cleaned = pipeline._clean_record(record)
        assert cleaned.title == ""
        assert cleaned.text == "Sample text"
    
    def test_does_not_modify_other_fields(self, storage, paths):
        pipeline = StandardizationPipeline(paths=paths, storage=storage)
        now = datetime.now()
        record = TextRecord(
            record_id="test-003",
            source="gdelt",
            source_type="news",
            title="Title",
            text="Text",
            published_at=now,
            retrieved_at=now,
            url="https://example.com",
            region="US"
        )
        cleaned = pipeline._clean_record(record)
        assert cleaned.url == "https://example.com"
        assert cleaned.region == "US"
        assert cleaned.record_id == "test-003"
        assert cleaned.source == "gdelt"
    
    def test_returns_same_record_object(self, storage, paths):
        """_clean_record modifies in place and returns the same object"""
        pipeline = StandardizationPipeline(storage=storage, paths=paths)
        now = datetime.now()
        record = TextRecord(
            record_id="test-004",
            source="gdelt",
            source_type="news",
            title="Title",
            text="text",
            published_at=now,
            retrieved_at=now
        )
        cleaned = pipeline._clean_record(record)
        assert cleaned is record

class TestRecordsToDataFrame:
    """Test the _records_to_dataframe method"""

    def test_empty_list_returns_empty_dataframe(self, storage, paths):
        pipeline = StandardizationPipeline(paths=paths, storage=storage)
        df = pipeline._records_to_dataframe([])
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
    
    def test_converts_text_records_to_dataframe(self, storage, paths):
        pipeline = StandardizationPipeline(storage=storage, paths=paths)
        now = datetime.now()
        records = [
            TextRecord(
                record_id="record 1", source="gdelt", source_type="news",
                title="Title 1", text="Text 1",
                published_at=now, retrieved_at=now
            ),
            TextRecord(
                record_id="record 2", source = "gdelt", source_type="news",
                title="Title 2", text="Text 2",
                published_at=now, retrieved_at=now
            ),
        ]
        df = pipeline._records_to_dataframe(records)
        assert len(df) == 2
        assert "record_id" in df.columns
        assert "text" in df.columns
    
    def test_dataframe_sorted_by_published_at(self, storage, paths):
        pipeline = StandardizationPipeline(storage=storage, paths=paths)
        early = datetime(2025, 1, 1)
        late = datetime(2026, 1, 1)
        records = [
            TextRecord(
                record_id="late", source="gdelt", title="Late",
                source_type="news", text="Late article",
                published_at=late, retrieved_at=late
            ),
            TextRecord(
                record_id="early", source = "gdelt", source_type="news",
                title="Early", text = "Early article",
                published_at=early, retrieved_at=early
            )
        ]
        df = pipeline._records_to_dataframe(records)
        assert df.iloc[0]["record_id"] == "early"
        assert df.iloc[1]["record_id"] == "late"

class TestDeduplicate:
    """Test the _deduplicate method"""

    def test_empty_dataframe_returns_empty(self, storage, paths):
        pipeline = StandardizationPipeline(storage=storage, paths=paths)
        df = pd.DataFrame([])
        result = pipeline._deduplicate(df)
        assert result.empty

    def test_no_record_id_column_returns_dedupe(self, storage, paths):
        pipeline = StandardizationPipeline(storage=storage, paths=paths)
        df = pd.DataFrame({"text": ["same", "same", "different"]})
        result = pipeline._deduplicate(df)
        assert len(result) == 2

    def test_drops_duplicate_record_ids(self, storage, paths):
        pipeline = StandardizationPipeline(paths=paths, storage=storage)
        df = pd.DataFrame({"record_id": ["pete", "repeat", "repeat"],
                           "text": ["first", "second", "third"]})
        result = pipeline._deduplicate(df)
        assert len(result.columns) == 2
        assert "pete" in result["record_id"].values
        assert "repeat" in result["record_id"].values

    def test_keeps_last_duplicate(self, storage, paths):
        pipeline = StandardizationPipeline(storage=storage, paths=paths)
        df = pd.DataFrame({
            "record_id": ["r1", "r1"],
            "text": ["old version", "new version"]
        })
        result = pipeline._deduplicate(df)
        assert len(result) == 1
        assert result.iloc[0]["text"] == "new version"
    
    def test_resets_index_after_dedupe(self, storage, paths):
        pipeline = StandardizationPipeline(storage=storage, paths=paths)
        df = pd.DataFrame({
            "record_id": ["r1", "r1", "r2"],
            "text": ["a", "b", "c"]
        })
        result = pipeline._deduplicate(df)
        assert list(result.index) == [0,1]
        


