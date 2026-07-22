from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

import logging
from typing import Any

import requests
from bs4 import BeautifulSoup

from eml_transformer.ingestion.base import TextSource
from eml_transformer.ingestion.registry import register_source
from eml_transformer.ingestion.schema import TextRecord
from eml_transformer.ingestion.sources.miso import MISONotificationSource
from eml_transformer.utils.dates import utc_now
from eml_transformer.utils.stamping import stable_hash

class TestHTMLToText:
    """Test the _HTML_to_text_helper"""

    def test_strips_html_tags(self, miso_source):
        result = miso_source._html_to_text("<p>Hello world</p>")
        assert result == "Hello world"

    def test_handles_nested_tags(self, miso_source):
        result = miso_source._html_to_text("<div><b>Bold</b> and <i>italic</i></div>")
        assert "Bold" in result
        assert "italic" in result
        assert "<div>" not in result
        assert "<b>" not in result
        assert "</div>" not in result
        assert "</div>" not in result
    
    def test_empty_string(self, miso_source):
        assert miso_source._html_to_text("") == ""
    
    def test_plain_text_unchanged(self, miso_source):
        assert miso_source._html_to_text("Plain text") == "Plain text"

class TestBuildURL:
    """Test the _build_url helper"""

    def test_returns_none_when_link_empty(self, miso_source):
        assert miso_source._build_url({"permanentLinkUrl": ""}) is None

    def test_returns_none_when_no_link(self, miso_source):
        assert miso_source._build_url({}) is None
    
    def test_absolute_url_unchanged(self, miso_source):
        notification = {"permanentLinkUrl": "/markets/notice/123"}
        result = miso_source._build_url(notification)
        assert result == "https://www.misoenergy.org/markets/notice/123"

    def test_relative_url_gets_prefixed(self, miso_source):
        notification = {"permanentLinkUrl": "/markets/notice/123"}
        result = miso_source._build_url(notification)
        assert result == "https://www.misoenergy.org/markets/notice/123"

class TestParseRecords:
    """Test the _parse_records method"""

    def test_empty_response_returns_empty_list(self, miso_source):
        result = miso_source._build_bronze_records([])

        assert result == []


    def test_builds_records_from_grouped_notifications(
        self,
        miso_source,
    ):
        first_notification = {
            "id": "1",
            "subject": "First",
        }
        second_notification = {
            "id": "2",
            "subject": "Second",
        }

        raw = [
            {
                "topic": "Market Notice",
                "notifications": [
                    first_notification,
                    second_notification,
                ],
            }
        ]

        result = miso_source._build_bronze_records(raw)

        assert len(result) == 2

        first, second = result

        first_fingerprint = stable_hash(
            {
                "subject": "First",
                "publish_date": None,
                "permanent_link": None,
            }
        )
        second_fingerprint = stable_hash(
            {
                "subject": "Second",
                "publish_date": None,
                "permanent_link": None,
            }
        )

        assert first.source == "miso_notifications"
        assert first.record_id == (
            f"miso:{first_fingerprint}"
        )
        assert first.raw == {
            "topic": "Market Notice",
            "notification": first_notification,
        }

        assert second.source == "miso_notifications"
        assert second.record_id == (
            f"miso:{second_fingerprint}"
        )
        assert second.raw == {
            "topic": "Market Notice",
            "notification": second_notification,
        }

    def test_builds_records_from_multiple_topics(
        self,
        miso_source,
    ):
        first_notification = {
            "subject": "First",
            "publishDate": "2026-01-15T12:00:00Z",
            "permanentLinkUrl": "/notifications/first",
        }
        second_notification = {
            "subject": "Second",
            "publishDate": "2026-01-16T12:00:00Z",
            "permanentLinkUrl": "/notifications/second",
        }

        raw = [
            {
                "topic": "Topic 1",
                "notifications": [first_notification],
            },
            {
                "topic": "Topic 2",
                "notifications": [second_notification],
            },
        ]

        result = miso_source._build_bronze_records(raw)

        assert len(result) == 2

        assert result[0].raw == {
            "topic": "Topic 1",
            "notification": first_notification,
        }
        assert result[0].record_id == miso_source._make_record_id(
            first_notification
        )

        assert result[1].raw == {
            "topic": "Topic 2",
            "notification": second_notification,
        }
        assert result[1].record_id == miso_source._make_record_id(
            second_notification
        )

    def test_skips_topic_with_no_notifications(
        self,
        miso_source,
    ):
        raw = [
            {
                "topic": "Topic 1",
                "notifications": [],
            },
            {
                "topic": "Topic 2",
                "notifications": [{"id": "1"}],
            },
        ]

        result = miso_source._build_bronze_records(raw)

        assert len(result) == 1
        assert result[0].raw["topic"] == "Topic 2"
        assert result[0].raw["notification"]["id"] == "1"

