import pytest
from datetime import datetime
from dataclasses import asdict
from eml_transformer.ingestion.schema import TextRecord, TEXT_RECORD_COLUMNS


class TestTextRecordCreation:
    """Test that TextRecord can be instantiated correctly."""

    def test_create_with_required_fields(self):
        now = datetime.now()
        record = TextRecord(
            record_id="test-001",
            source="gdelt",
            source_type="news",
            title="Test Article",
            text="This is a test article body.",
            published_at=now,
            retrieved_at=now,
        )
        assert record.record_id == "test-001"
        assert record.source == "gdelt"
        assert record.source_type == "news"
        assert record.title == "Test Article"
        assert record.text == "This is a test article body."
        assert record.published_at == now
        assert record.retrieved_at == now

    def test_optional_fields_default_to_none(self):
        now = datetime.now()
        record = TextRecord(
            record_id="test-002",
            source="gdelt",
            source_type="news",
            title=None,
            text="Body text.",
            published_at=None,
            retrieved_at=now,
        )
        assert record.url is None
        assert record.region is None
        assert record.title is None
        assert record.published_at is None

    def test_list_and_dict_defaults_are_empty(self):
        now = datetime.now()
        record = TextRecord(
            record_id="test-003",
            source="gdelt",
            source_type="news",
            title="Test",
            text="Body.",
            published_at=now,
            retrieved_at=now,
        )
        assert record.categories == []
        assert record.metadata == {}
        assert record.raw == {}

    def test_list_and_dict_defaults_are_independent(self):
        """Ensure each instance gets its own list/dict, not a shared reference."""
        now = datetime.now()
        r1 = TextRecord(record_id="a", source="s", source_type="t", title="T", text="X", published_at=now, retrieved_at=now)
        r2 = TextRecord(record_id="b", source="s", source_type="t", title="T", text="X", published_at=now, retrieved_at=now)
        r1.categories.append("energy")
        r1.metadata["key"] = "value"
        assert r2.categories == []
        assert r2.metadata == {}


class TestTextRecordToDict:
    """Test the to_dict method."""

    def test_to_dict_returns_all_fields(self):
        now = datetime.now()
        record = TextRecord(
            record_id="test-004",
            source="gdelt",
            source_type="news",
            title="Test",
            text="Body.",
            published_at=now,
            retrieved_at=now,
        )
        d = record.to_dict()
        assert isinstance(d, dict)
        assert d["record_id"] == "test-004"
        assert d["source"] == "gdelt"
        assert d["categories"] == []
        assert d["metadata"] == {}

    def test_to_dict_matches_asdict(self):
        now = datetime.now()
        record = TextRecord(
            record_id="test-005",
            source="gdelt",
            source_type="news",
            title="Test",
            text="Body.",
            published_at=now,
            retrieved_at=now,
        )
        assert record.to_dict() == asdict(record)


class TestTextRecordColumns:
    """Test that TEXT_RECORD_COLUMNS matches the dataclass fields."""

    def test_columns_match_dataclass_fields(self):
        field_names = [f.name for f in TextRecord.__dataclass_fields__.values()]
        assert TEXT_RECORD_COLUMNS == field_names

    def test_column_count(self):
        assert len(TEXT_RECORD_COLUMNS) == 12