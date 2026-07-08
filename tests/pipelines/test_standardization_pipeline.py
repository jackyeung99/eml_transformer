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
        
class TestRunSource:
    """Test the run_source method"""

    def test_skips_when_no_bronze_data(self, storage, paths):
        pipeline = StandardizationPipeline(storage=storage, paths=paths)
        result = pipeline.run_source("gdelt", {})

        assert result.status == "skipped"
        assert result.records_read == 0 
        assert result.records_out == 0
        assert "No bronze data" in result.error

    @patch("eml_transformer.pipelines.standardization_pipeline.create_source")
    def test_successful_run(self, mock_create_source, storage, paths):
        mock_source = MagicMock()
        mock_source.name = "gdelt"
        now = datetime.now()
        mock_source.standardize_record.return_value = TextRecord(
            record_id="r1", source="gdelt", source_type="news", 
            title="Test Title", text="Test Text", 
            published_at=now, retrieved_at=now
        )
        mock_create_source.return_value = mock_source

        bronze_key = paths.bronze_records(source="gdelt")
        storage.write_jsonl(
            [{"raw": {"title": "Test Title", "text": "Test text"}}],
            bronze_key
        )

        pipeline = StandardizationPipeline(storage=storage, paths=paths)
        result = pipeline.run_source("gdelt", {})

        assert result.status == "success"
        assert result.records_read == 1
        assert result.records_out == 1
        assert result.records_failed == 0
        silver_key = paths.silver_records(source="gdelt")
        assert silver_key in storage.data

    @patch("eml_transformer.pipelines.standardization_pipeline.create_source")
    def test_counts_failed_records(self, mock_create_source, storage, paths):
        mock_source = MagicMock()
        mock_source.name = "gdelt"
        now = datetime.now()
        mock_source.standardize_record.side_effect = [
            TextRecord(
                record_id="r1", source="gdelt", source_type="news",
                title="Good", text="Good text",
                published_at=now, retrieved_at=now
            ),
            Exception("Bad record")
        ]
        mock_create_source.return_value = mock_source

        bronze_key = paths.bronze_records(source="gdelt")
        storage.write_jsonl(
            [
                {"raw": {"title": "Good", "text": "Good text"}},
                {"raw": {"title": "Bad", "text": "Bad text"}}
            ],
            bronze_key
        )

        pipeline = StandardizationPipeline(storage=storage, paths=paths)
        result = pipeline.run_source("gdelt", {})

        assert result.status == "success"
        assert result.records_read == 2
        assert result.records_failed == 1

    @patch("eml_transformer.pipelines.standardization_pipeline.create_source")
    def test_no_parquet_written_when_all_fail(self, mock_create_source, storage, paths):
        mock_source = MagicMock()
        mock_source.name = "gdelt"
        mock_source.standardize_record.side_effect = Exception("All bad")
        mock_create_source.return_value = mock_source

        bronze_key = paths.bronze_records(source="gdelt")
        storage.write_jsonl(
            [{"raw": {"title": "Bad", "text": "Bad text"}}],
            bronze_key
        )

        pipeline = StandardizationPipeline(storage=storage, paths=paths)
        result = pipeline.run_source("gdelt", {})

        assert result.status == "success"
        assert result.records_failed == 1
        assert result.records_out == 0
        silver_key = paths.silver_records(source="gdelt")
        assert silver_key not in storage.data
    
    @patch("eml_transformer.pipelines.standardization_pipeline.create_source")
    def test_returns_failed_on_exception(self, mock_create_source, storage, paths):
        mock_create_source.side_effect = Exception("Source not found")

        pipeline = StandardizationPipeline(storage=storage, paths=paths)
        result = pipeline.run_source("bad source", {})

        assert result.status == "failed"
        assert result.records_read == 0
        assert result.records_out == 0
        assert "Source not found" in result.error
    
class TestRunAll:
    """Test the run_all method"""

    def test_returns_empty_list_for_empty_configs(self, storage, paths):
        pipeline = StandardizationPipeline(storage=storage, paths=paths)
        result = pipeline.run_all({})
        assert result == []
    
    def test_calls_run_source_for_each_config(self, storage, paths):
        pipeline = StandardizationPipeline(storage=storage, paths=paths)
        pipeline.run_source = MagicMock(return_value=StandardizationResult(
            status="success",
            source="fake",
            records_read=1,
            records_out=1
        ))

        configs = {
            "gdelt": {"param1": "value1"},
            "iemafos": {"param2": "value2"}
        }
        results = pipeline.run_all(configs)

        assert len(results) == 2
        assert pipeline.run_source.call_count == 2
        pipeline.run_source.assert_any_call("gdelt", {"param1": "value1"})
        pipeline.run_source.assert_any_call("iemafos", {"param2": "value2"})
    
    def test_returns_all_results_even_when_some_fail(self, storage, paths):
        pipeline = StandardizationPipeline(storage=storage, paths=paths)

        pipeline.run_source = MagicMock(side_effect=[
            StandardizationResult(
                status="success", source="gdelt",
                records_read=10, records_out=10,
            ),
            StandardizationResult(
                status="failed", source="iemafos",
                records_read=0, records_out=0,
                error="Something broke",
            ),
        ])

        configs = {"gdelt": {}, "iemafos": {}}
        results = pipeline.run_all(configs)

        assert len(results) == 2
        assert results[0].status == "success"
        assert results[1].status == "failed"

    def test_preserves_config_order(self, storage, paths):
        pipeline = StandardizationPipeline(storage=storage, paths=paths)

        pipeline.run_source = MagicMock(side_effect=[
            StandardizationResult(status="success", source="a", records_read=1, records_out=1),
            StandardizationResult(status="success", source="b", records_read=1, records_out=1),
            StandardizationResult(status="success", source="c", records_read=1, records_out=1),
        ])

        configs = {"a": {}, "b": {}, "c": {}}
        results = pipeline.run_all(configs)

        assert [r.source for r in results] == ["a", "b", "c"]