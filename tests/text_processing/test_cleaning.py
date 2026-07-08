import pytest
import pandas as pd
from eml_transformer.text_processing.cleaning import (
    strip_html,
    normalize_unicode,
    normalize_whitespace,
    remove_empty_lines,
    truncate_text,
    clean_text
)
import re
import unicodedata
from bs4 import BeautifulSoup

class TestStripHTML:
    """Test HTML tag removal"""

    def test_removes_basic_tags(self):
        assert strip_html("<p>Hello World!</p>") == "Hello World!"

    def test_removes_nested_tags(self):
        result = strip_html("<div><b>Bold</b> text</div>")
        assert "Bold" in result
        assert "<div>" not in result
        assert "</div>" not in result
        assert "<b>" not in result
        assert "</b>" not in result
        
    def test_plain_text_unchanged(self):
        assert strip_html("No tags here") == "No tags here"
    
    def test_separates_elements_with_space(self):
        result = strip_html("<p>First</p><p>Second</p>")
        assert "First" in result
        assert "Second" in result
    
class TestNormalizeUnicode:
    """Test unicode normalization"""

    def test_normalizes_fancy_characters(self):
        result = normalize_unicode("\ufb01nance") #finance
        assert result == "finance"
    
    def test_plain_ascii_unchanged(self):
        assert normalize_unicode("hello world") == "hello world"

class TestNormalizeWhitespace:
    """Test whitespace normalization"""

    def test_reduces_multiple_spaces(self):
        assert normalize_whitespace("hello    world") == "hello world"
    
    def test_collapses_tabs_and_newlines(self):
        assert normalize_whitespace(" hello\t\n world") == "hello world"

    def test_strips_leading_trailing_whitespace(self):
        assert normalize_whitespace("  hello world") == "hello world"
    
    def test_single_space_unchanged(self):
        assert normalize_whitespace("hello world") == "hello world"

class TestRemoveEmptyLines:
    """"Test empty line removal"""

    def test_removes_empty_lines(self):
        text = "line one\n\n\nline two"
        assert remove_empty_lines(text) == "line one\nline two"

    def test_single_line_unchanged(self):
        text = "just one line"
        assert remove_empty_lines(text) == "just one line"
    
    def test_strips_whitespace_only_lines(self):
        text = "line one\n   \nline two"
        assert remove_empty_lines(text) == "line one\nline two"

class TestTruncateText:
    """Test text truncation"""

    def test_character_limit(self):
        text = "a" *10000
        result = truncate_text(text)
        assert len(result) == 8000
    
    def test_short_text_unchanged(self):
        text = "short"
        assert truncate_text(text) == "short"

    def test_custom_char_limit(self):
        text = "hello world"
        assert truncate_text(text, max_chars=5) == "hello"
    
    def test_exact_limit_unchanged(self):
        text = "a" * 8000
        assert truncate_text(text) == text

class TestCleanText:
    """Tests text cleaning pipeline"""

    def test_strips_html_and_normalizes(self):
        result = clean_text("<p>Hello     world</p>")
        assert result == "Hello world"

    def test_handles_empty_string(self):
        assert clean_text("") == ""
    
    def test_full_pipeline(self):
        messy = "  <div>  Hello     world  </div> "
        result = clean_text(messy)
        assert "Hello" in result
        assert "world" in result
        assert "<div>" not in result
        assert "</div>" not in result

    def truncates_long_text(self):
        text = "<p>" + "a" * 10000 + "</p>"
        result = clean_text(text)
        assert len(result) == 8000