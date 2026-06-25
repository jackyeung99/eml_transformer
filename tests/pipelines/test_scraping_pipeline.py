import pandas as pd
import pytest

from eml_transformer.pipelines.scraping_pipeline import ScrapingPipeline


def test_select_records_skips_success_forbidden_not_found(storage, paths):
    
    pipeline = ScrapingPipeline(
        storage=storage,
        paths=paths,
    )

    input_df = pd.DataFrame([
        {"record_id": "1", "url": "https://a.com"},
        {"record_id": "2", "url": "https://b.com"},
        {"record_id": "3", "url": "https://c.com"},
        {"record_id": "4", "url": "https://d.com"},
    ])

    existing_df = pd.DataFrame([
        {"record_id": "1", "scrape_status": "success"},
        {"record_id": "2", "scrape_status": "forbidden"},
        {"record_id": "3", "scrape_status": "failed"},
    ])

    result = pipeline._select_records_to_scrape(
        input_df=input_df,
        existing_df=existing_df,
        retry_failed=True,
    )

    assert result["record_id"].tolist() == ["3", "4"]


def test_select_records_does_not_retry_failed_when_disabled(storage, paths):
    pipeline = ScrapingPipeline(
        storage=storage,
        paths=paths,
    )
       

    input_df = pd.DataFrame([
        {"record_id": "1", "url": "https://a.com"},
        {"record_id": "2", "url": "https://b.com"},
    ])

    existing_df = pd.DataFrame([
        {"record_id": "1", "scrape_status": "failed"},
    ])

    result = pipeline._select_records_to_scrape(
        input_df=input_df,
        existing_df=existing_df,
        retry_failed=False,
    )

    assert result["record_id"].tolist() == ["2"]


def test_merge_record_prefers_scraped_published_at(storage, paths):
        
    pipeline = ScrapingPipeline(
        storage=storage,
        paths=paths,
    )

    row = pipeline._merge_record_and_scrape_result(

        record_dict={
            "record_id": "1",
            "url": "https://example.com",
            "published_at": "2026-01-01T00:00:00Z",
            "metadata": {"source": "gdelt"},
        },
        scrape_result={
            "scrape_status": "success",
            "title": " Title ",
            "text": " Body ",
            "published_at": "2026-01-01T12:34:00Z",
            "metadata": {"published_at_source": "json_ld"},
        },
    )

    assert row["published_at"] == "2026-01-01T12:34:00Z"
    assert row["metadata"]["original_published_at"] == "2026-01-01T00:00:00Z"
    assert row["metadata"]["scraped_published_at"] == "2026-01-01T12:34:00Z"
    assert row["metadata"]["published_at_source"] == "json_ld"
    assert row["metadata"]["has_scraped_published_at"] is True


def test_clean_only_cleans_successful_records(storage, paths):
    pipeline = ScrapingPipeline(
        storage=storage,
        paths=paths,
    )

    success = pipeline._clean_scraped_record({
        "scrape_status": "success",
        "title": "  Hello\n\nWorld ",
        "text": "  This   is\ntext ",
        "metadata": None,
    })

    failed = pipeline._clean_scraped_record({
        "scrape_status": "failed",
        "title": "  Bad\nTitle ",
        "text": "",
        "metadata": None,
    })

    assert success["title"]
    assert success["text_length"] == len(success["text"])
    assert success["metadata"] == {}

    assert failed["title"] == "  Bad\nTitle "
    assert failed["text_length"] == 0


def test_merge_scraped_results_keeps_latest_record_id(storage, paths):
    pipeline = ScrapingPipeline(
        storage=storage,
        paths=paths,
    )


    existing_df = pd.DataFrame([
        {"record_id": "1", "scrape_status": "failed"},
        {"record_id": "2", "scrape_status": "success"},
    ])

    scraped_df = pd.DataFrame([
        {"record_id": "1", "scrape_status": "success"},
    ])

    result = pipeline._merge_scraped_results(existing_df, scraped_df)

    assert len(result) == 2
    assert result.loc[result["record_id"] == "1", "scrape_status"].iloc[0] == "success"



def test_merge_replaces_published_at_with_scraped_value(storage, paths):
    pipeline = ScrapingPipeline(
        storage=storage,
        paths=paths,
    )

    row = pipeline._merge_record_and_scrape_result(
        record_dict={
            "record_id": "gdelt-1",
            "url": "https://example.com/article",
            "published_at": "2026-06-24T12:00:00Z",
            "metadata": {
                "source": "gdelt",
            },
        },
        scrape_result={
            "success": True,
            "scrape_status": "success",
            "title": "Storm causes outage",
            "text": "Thousands lost power.",
            "published_at": "2026-06-24T12:30:00Z",
            "metadata": {
                "method": "trafilatura",
                "published_at_source": "json_ld",
            },
        },
    )

    assert row["published_at"] == "2026-06-24T12:30:00Z"

    assert row["metadata"]["original_published_at"] == "2026-06-24T12:00:00Z"
    assert row["metadata"]["scraped_published_at"] == "2026-06-24T12:30:00Z"
    assert row["metadata"]["final_published_at"] == "2026-06-24T12:30:00Z"
    assert row["metadata"]["published_at_source"] == "json_ld"
    assert row["metadata"]["has_scraped_published_at"] is True
    assert row["metadata"]["has_precise_published_at"] is True


def test_merge_keeps_original_published_at_when_scraped_missing(storage, paths):
    pipeline = ScrapingPipeline(
        storage=storage,
        paths=paths,
    )

    row = pipeline._merge_record_and_scrape_result(
        record_dict={
            "record_id": "gdelt-1",
            "url": "https://example.com/article",
            "published_at": "2026-06-24T12:00:00Z",
            "metadata": {},
        },
        scrape_result={
            "success": True,
            "scrape_status": "success",
            "title": "Storm causes outage",
            "text": "Thousands lost power.",
            "published_at": None,
            "metadata": {
                "method": "trafilatura",
            },
        },
    )

    assert row["published_at"] == "2026-06-24T12:00:00Z"

    assert row["metadata"]["original_published_at"] == "2026-06-24T12:00:00Z"
    assert row["metadata"]["scraped_published_at"] is None
    assert row["metadata"]["final_published_at"] == "2026-06-24T12:00:00Z"
    assert row["metadata"]["published_at_source"] == "source_record"
    assert row["metadata"]["has_scraped_published_at"] is False
    assert row["metadata"]["has_precise_published_at"] is True


def test_merge_skips_published_at_with_scraped_value(storage, paths):
    pipeline = ScrapingPipeline(
        storage=storage,
        paths=paths,
    )

    row = pipeline._merge_record_and_scrape_result(
        record_dict={
            "record_id": "gdelt-1",
            "url": "https://example.com/article",
            "published_at": "2026-06-24T12:00:00Z",
            "metadata": {
                "source": "gdelt",
                "has_precise_published_at": True
            },
        },
        scrape_result={
            "success": True,
            "scrape_status": "success",
            "title": "Storm causes outage",
            "text": "Thousands lost power.",
            "published_at": "2026-06-24T12:30:00Z",
            "metadata": {
                "method": "trafilatura",
                "published_at_source": "json_ld",
            },
        },
    )

    assert row["published_at"] == "2026-06-24T12:00:00Z"

    assert row["metadata"]["original_published_at"] == "2026-06-24T12:00:00Z"
    assert row["metadata"]["scraped_published_at"] is "2026-06-24T12:30:00Z"
    assert row["metadata"]["final_published_at"] == "2026-06-24T12:00:00Z"
    assert row["metadata"]["published_at_source"] == "source_record_precise"
    assert row["metadata"]["has_scraped_published_at"] is True
    assert row["metadata"]["has_precise_published_at"] is True

