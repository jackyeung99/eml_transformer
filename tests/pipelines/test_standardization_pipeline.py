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

    
    
