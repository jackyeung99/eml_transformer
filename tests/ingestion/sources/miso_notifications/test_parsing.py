from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

import logging
from typing import Any

import requests
from bs4 import BeautifulSoup

from eml_transformer.ingestion.base import TextSource
from eml_transformer.ingestion.registry import register_source
from eml_transformer.ingestion.schema import TextRecord, utc_now
from eml_transformer.ingestion.sources.miso import MISONotificationSource

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
        result = miso_source._parse_records([])
        assert result == []
    
    def test_parses_grouped_notifications(self, miso_source):
        raw = [
            {
                "topic": "Market Notice",
                "notifications": [
                    {"id": "1", "subject": "First"},
                    {"id": "2", "subject": "Second"}
                ]
            }
        ]
        result = miso_source._parse_records(raw)
        assert len(result) == 2
        assert result[0]["topic"] == "Market Notice"
        assert result[0]["notification"]["id"] == "1"
        assert result[1]["notification"]["id"] == "2"
    
    def test_handles_multiple_topics(self, miso_source):
        raw = [
            {"topic": "Topic 1", "notifications": [{"id": "1"}]},
            {"topic": "Topic 2", "notifications": [{"id": "2"}]}
        ]
        result = miso_source._parse_records(raw)
        assert len(result) == 2
        assert result[0]["topic"] == "Topic 1"
        assert result[1]["topic"] == "Topic 2"
    
    def test_handles_topic_with_no_notifications(self, miso_source):
        raw = [
            {"topic": "Topic 1", "notifications": []},
            {"topic": "Topic 2", "notifications": [{"id": "1"}]}
        ]
        result = miso_source._parse_records(raw)
        assert len(result) == 1
        assert result[0]["topic"] == "Topic 2"

