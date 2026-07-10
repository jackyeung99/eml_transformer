import pytest
from eml_transformer.ingestion.schema import TextRecord


class TestStandardizeRecord:
    """Test the standardize_record method"""

    def test_returns_text_record(self, newsapi_source, newsapi_make_article):
        record = newsapi_source.standardize_record(newsapi_make_article())
        assert isinstance(record, TextRecord)

    def test_maps_basic_fields(self, newsapi_source, newsapi_make_article):
        record = newsapi_source.standardize_record(newsapi_make_article())
        assert record.source == "newsapi"
        assert record.source_type == "api"
        assert record.title == "Storm hits coast"
        assert record.url == "https://example.com/article-1"
        assert record.published_at == "2026-01-15T12:00:00Z"
        assert record.region is None
    
    def test_combines_title_description_content_into_text(self, newsapi_source, newsapi_make_article):
        record = newsapi_source.standardize_record(newsapi_make_article())
        assert "Storm hits coast" in record.text
        assert "A severe storm caused damage." in record.text
        assert "Full article content here." in record.text
    
    def test_skips_none_parts_in_text(self, newsapi_source, newsapi_make_article):
        article = newsapi_make_article(description = None, content = None)
        record = newsapi_source.standardize_record(article)
        assert record.text == "Storm hits coast"
        assert "None" not in record.text
    
    def test_skips_empty_parts_in_text(self, newsapi_source, newsapi_make_article):
        article = newsapi_make_article(description = "", content = "")
        record = newsapi_source.standardize_record(article)
        assert record.text == "Storm hits coast"

    def test_handles_all_fields_missing(self, newsapi_source, newsapi_make_article):
        article = newsapi_make_article(title=None, description=None, content=None)
        record = newsapi_source.standardize_record(article)
        assert record.text == ""
    
    def test_categories_contains_news(self, newsapi_source, newsapi_make_article):
        record = newsapi_source.standardize_record(newsapi_make_article())
        assert record.categories == ["news"]

    def test_metadata_captures_source_and_querty_info(self, newsapi_source, newsapi_make_article):
        record = newsapi_source.standardize_record(newsapi_make_article())
        assert record.metadata["news_source"] == "CNN"
        assert record.metadata["news_source_id"] == "cnn"
        assert record.metadata["author"] == "John Reporter"
        assert record.metadata["query"] == "storm"
        assert record.metadata["language"] == "en"
        assert record.metadata["sort_by"] == "relevancy"
    
    def test_handles_missing_source_dict(self, newsapi_source, newsapi_make_article):
        article = newsapi_make_article(source=None)
        record = newsapi_source.standardize_record(article)
        assert record.metadata["news_source"] is None
        assert record.metadata["news_source_id"] is None
    
    def test_raw_field_contains_full_article(self, newsapi_source, newsapi_make_article):
        article = newsapi_make_article()
        record = newsapi_source.standardize_record(article)
        assert record.metadata["news_source"] is None
        assert record.metadata["news_source_id"] is None

    def test_raw_field_contains_full_article(self, newsapi_source, newsapi_make_article):
        article = newsapi_make_article()
        record = newsapi_source.standardize_record(article)
        assert record.raw == article

    def test_retrieved_at_is_set(self, newsapi_source, newsapi_make_article):
        record = newsapi_source.standardize_record(newsapi_make_article())
        assert record.record_id is not None
        assert len(record.record_id) > 0

    def test_different_articles_get_different_ids(self, newsapi_source, newsapi_make_article):
        article1 = newsapi_make_article(url="https://example.com/1", title="First")
        article2 = newsapi_make_article(url="https://example.com/2", title="Second")
        record1 = newsapi_source.standardize_record(article1)
        record2 = newsapi_source.standardize_record(article2)
        assert record1.record_id != record2.record_id


    