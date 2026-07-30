'''
set of helper functions to clean textual data

'''
import re
import unicodedata

from bs4 import BeautifulSoup


WHITESPACE_PATTERN = re.compile(r"\s+")
HTML_TAG_PATTERN = re.compile(r"<[a-zA-Z!/][^>]*>")


def strip_html(text: str) -> str:
    if not HTML_TAG_PATTERN.search(text):
        return text

    return BeautifulSoup(
        text,
        "html.parser",
    ).get_text(separator=" ")


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def normalize_whitespace(text: str) -> str:
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def truncate_text(
    text: str,
    max_chars: int = 8000,
) -> str:
    return text[:max_chars]


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = strip_html(text)
    text = normalize_unicode(text)
    text = normalize_whitespace(text)

    return truncate_text(text)