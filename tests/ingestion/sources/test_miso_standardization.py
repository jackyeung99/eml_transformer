import pytest
from datetime import datetime
from eml_transformer.ingestion.sources.miso import MISONotificationSource
from eml_transformer.ingestion.schema import TextRecord



class TestStandardizeRecord:
    """Test the standardize_record method."""


    def test_returns_text_record(self, miso_source, miso_make_raw_record):
        record = miso_source.standardize_record(miso_make_raw_record())
        assert isinstance(record, TextRecord)

    def test_maps_basic_fields(self, miso_source, miso_make_raw_record):
        raw = miso_make_raw_record()
        record = miso_source.standardize_record(raw)
        assert record.source == "miso_notifications"
        assert record.source_type == "api"
        assert record.title == "Market Notice"
        assert record.published_at == "2026-01-15T12:00:00Z"
        assert record.region == "MISO"

    def test_body_html_is_converted_to_text(self, miso_source, miso_make_raw_record):
        raw = miso_make_raw_record(body="<p>Hello <b>world</b></p>")
        record = miso_source.standardize_record(raw)
        assert "<" not in record.text
        assert "Hello" in record.text
        assert "world" in record.text

    def test_handles_empty_body(self, miso_source, miso_make_raw_record):
        raw = miso_make_raw_record(body="")
        record = miso_source.standardize_record(raw)
        assert record.text == ""

    def test_handles_none_body(self, miso_source, miso_make_raw_record):
        raw = miso_make_raw_record(body=None)
        record = miso_source.standardize_record(raw)
        assert record.text == ""

    def test_builds_url_from_relative_link(self, miso_source, miso_make_raw_record):
        raw = miso_make_raw_record(permanentLinkUrl="/markets/notice/456")
        record = miso_source.standardize_record(raw)
        assert record.url == "https://www.misoenergy.org/markets/notice/456"

    def test_uses_absolute_url_directly(self, miso_source, miso_make_raw_record):
        raw = miso_make_raw_record(permanentLinkUrl="https://example.com/notice")
        record = miso_source.standardize_record(raw)
        assert record.url == "https://example.com/notice"

    def test_categories_include_topic_and_marker(self, miso_source, miso_make_raw_record):
        raw = {
            "topic": "Emergency Alert",
            "notification": {
                "id": "n1",
                "subject": "Alert",
                "publishDate": "2026-01-15T12:00:00Z",
                "body": "body",
            },
        }
        record = miso_source.standardize_record(raw)
        assert "market_notice" in record.categories
        assert "Emergency Alert" in record.categories

    def test_metadata_captures_topic_and_id(self, miso_source, miso_make_raw_record):
        raw = miso_make_raw_record()
        record = miso_source.standardize_record(raw)
        assert record.metadata["topic"] == "Market Notice"
        assert record.metadata["notification_id"] == "notif-123"
        assert record.metadata["publish_date"] == "2026-01-15T12:00:00Z"

    def test_raw_field_contains_full_notification(self, miso_source, miso_make_raw_record):
        raw = miso_make_raw_record()
        record = miso_source.standardize_record(raw)
        assert record.raw == raw["notification"]

    def test_retrieved_at_is_set(self, miso_source, miso_make_raw_record):
        raw = miso_make_raw_record()
        record = miso_source.standardize_record(raw)
        assert record.retrieved_at is not None

    def test_record_id_is_generated(self, miso_source, miso_make_raw_record):
        raw = miso_make_raw_record()
        record = miso_source.standardize_record(raw)
        assert record.record_id is not None
        assert len(record.record_id) > 0

    def test_different_notifications_get_different_ids(self, miso_source, miso_make_raw_record):
        raw1 = miso_make_raw_record(id="notif-1", subject="First")
        raw2 = miso_make_raw_record(id="notif-2", subject="Second")
        record1 = miso_source.standardize_record(raw1)
        record2 = miso_source.standardize_record(raw2)
        assert record1.record_id != record2.record_id