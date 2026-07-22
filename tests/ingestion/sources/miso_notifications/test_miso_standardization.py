from datetime import datetime, timezone
from typing import Any

from eml_transformer.ingestion.schema import BronzeRecord, TextRecord


PUBLISHED_AT = datetime(
    2026,
    1,
    15,
    12,
    0,
    tzinfo=timezone.utc,
)

RETRIEVED_AT = datetime(
    2026,
    1,
    15,
    12,
    5,
    tzinfo=timezone.utc,
)


def make_miso_bronze_record(
    *,
    record_id: str = "notif-123",
    published_at: datetime = PUBLISHED_AT,
    retrieved_at: datetime = RETRIEVED_AT,
    topic: str = "Market Notice",
    **notification_overrides: Any,
) -> BronzeRecord:
    notification = {
        "id": record_id,
        "subject": "Market Notice",
        "publishDate": "2026-01-15T12:00:00Z",
        "body": "<p>Notification body</p>",
        "permanentLinkUrl": "/markets/notice/123",
    }
    notification.update(notification_overrides)

    return BronzeRecord(
        source="miso_notifications",
        record_id=record_id,
        published_at=published_at,
        retrieved_at=retrieved_at,
        raw={
            "topic": topic,
            "notification": notification,
        },
    )


class TestStandardizeRecord:
    """Tests for converting MISO bronze records to text records."""

    def test_maps_basic_fields(self, miso_source):
        bronze = make_miso_bronze_record()

        record = miso_source.standardize_record(bronze)

        assert record.source == "miso_notifications"
        assert record.source_type == "api"
        assert record.title == "Market Notice"
        assert record.published_at == PUBLISHED_AT
        assert record.retrieved_at == RETRIEVED_AT
        assert record.region == "MISO"

    def test_body_html_is_converted_to_text(
        self,
        miso_source,
    ):
        bronze = make_miso_bronze_record(
            body="<p>Hello <b>world</b></p>",
        )

        record = miso_source.standardize_record(bronze)

        assert "<" not in record.text
        assert "Hello" in record.text
        assert "world" in record.text

    def test_handles_empty_body(self, miso_source):
        bronze = make_miso_bronze_record(body="")

        record = miso_source.standardize_record(bronze)

        assert record.text == ""

    def test_handles_none_body(self, miso_source):
        bronze = make_miso_bronze_record(body=None)

        record = miso_source.standardize_record(bronze)

        assert record.text == ""

    def test_builds_url_from_relative_link(
        self,
        miso_source,
    ):
        bronze = make_miso_bronze_record(
            permanentLinkUrl="/markets/notice/456",
        )

        record = miso_source.standardize_record(bronze)

        assert record.url == (
            "https://www.misoenergy.org"
            "/markets/notice/456"
        )

    def test_uses_absolute_url_directly(
        self,
        miso_source,
    ):
        bronze = make_miso_bronze_record(
            permanentLinkUrl=(
                "https://example.com/notice"
            ),
        )

        record = miso_source.standardize_record(bronze)

        assert record.url == (
            "https://example.com/notice"
        )

    def test_categories_include_topic_and_marker(
        self,
        miso_source,
    ):
        bronze = make_miso_bronze_record(
            record_id="n1",
            topic="Emergency Alert",
            subject="Alert",
            body="body",
        )

        record = miso_source.standardize_record(bronze)

        assert "market_notice" in record.categories
        assert "Emergency Alert" in record.categories

    def test_metadata_captures_topic_and_id(
        self,
        miso_source,
    ):
        bronze = make_miso_bronze_record()

        record = miso_source.standardize_record(bronze)

        assert record.metadata["topic"] == "Market Notice"
        assert (
            record.metadata["notification_id"]
            == "notif-123"
        )
        assert record.metadata["publish_date"] == (
            "2026-01-15T12:00:00Z"
        )

    def test_raw_field_contains_source_data(
        self,
        miso_source,
    ):
        bronze = make_miso_bronze_record()

        record = miso_source.standardize_record(bronze)

        assert record.raw == bronze.raw

    def test_preserves_retrieved_at(
        self,
        miso_source,
    ):
        bronze = make_miso_bronze_record()

        record = miso_source.standardize_record(bronze)

        assert record.retrieved_at == bronze.retrieved_at
        assert record.retrieved_at.tzinfo is not None

    def test_preserves_record_id(
        self,
        miso_source,
    ):
        bronze = make_miso_bronze_record(
            record_id="notif-123",
        )

        record = miso_source.standardize_record(bronze)

        assert record.record_id == "notif-123"

    def test_different_bronze_ids_are_preserved(
        self,
        miso_source,
    ):
        first = make_miso_bronze_record(
            record_id="notif-1",
            subject="First",
        )
        second = make_miso_bronze_record(
            record_id="notif-2",
            subject="Second",
        )

        first_record = miso_source.standardize_record(
            first
        )
        second_record = miso_source.standardize_record(
            second
        )

        assert (
            first_record.record_id
            != second_record.record_id
        )