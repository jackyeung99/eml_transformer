import pytest

from eml_transformer.extraction.scraper import (
    ArticleScraperConfig,
    HybridArticleScraper,
)


@pytest.fixture
def scraper():
    return HybridArticleScraper(
        ArticleScraperConfig(
            request_timeout=1,
            playwright_timeout=1_000,
            fallback_on_forbidden=False,
        )
    )


@pytest.fixture
def html_with_published_time():
    return """
    <html>
      <head>
        <meta property="article:published_time"
              content="2026-06-24T12:30:00Z" />
      </head>
      <body>
        <article>
          <h1>Storm causes outage</h1>
          <p>Thousands lost power.</p>
        </article>
      </body>
    </html>
    """


def test_extract_published_at_with_bs4(scraper, html_with_published_time):
    published_at = scraper._extract_published_at_with_bs4(
        html_with_published_time
    )

    assert published_at == "2026-06-24T12:30:00Z"


def test_extract_published_at_from_time_tag(scraper):
    html = """
    <html>
      <body>
        <time datetime="2026-06-24T14:15:00Z">
          June 24, 2026
        </time>
      </body>
    </html>
    """

    published_at = scraper._extract_published_at_with_bs4(html)

    assert published_at == "2026-06-24T14:15:00Z"


def test_bs4_ignores_date_only_timestamp(scraper):
    html = """
    <html>
      <head>
        <meta property="article:published_time" content="2026-06-24" />
      </head>
    </html>
    """

    assert scraper._extract_published_at_with_bs4(html) is None


def test_bs4_accepts_precise_timestamp(scraper):
    html = """
    <html>
      <head>
        <meta property="article:published_time"
              content="2026-06-24T12:30:00Z" />
      </head>
    </html>
    """

    assert scraper._extract_published_at_with_bs4(html) == "2026-06-24T12:30:00Z"