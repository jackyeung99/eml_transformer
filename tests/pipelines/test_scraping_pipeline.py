import pandas as pd

from eml_transformer.pipelines.scraping_pipeline import ScrapingPipeline


def test_select_records_skips_success_forbidden_not_found(storage, paths):
    pipeline = ScrapingPipeline(storage=storage, paths=paths)

    input_df = pd.DataFrame([
        {"record_id": "1", "url": "https://a.com"},
        {"record_id": "2", "url": "https://b.com"},
        {"record_id": "3", "url": "https://c.com"},
        {"record_id": "4", "url": "https://d.com"},
    ])

    existing_df = pd.DataFrame([
        {"record_id": "1", "metadata": {"scraping": {"status": "success"}}},
        {"record_id": "2", "metadata": {"scraping": {"status": "forbidden"}}},
        {"record_id": "3", "metadata": {"scraping": {"status": "failed"}}},
    ])

    result = pipeline._select_records_to_scrape(
        input_df=input_df,
        existing_df=existing_df,
        retry_failed=True,
    )

    assert result["record_id"].tolist() == ["3", "4"]


def test_select_records_does_not_retry_failed_when_disabled(storage, paths):
    pipeline = ScrapingPipeline(storage=storage, paths=paths)

    input_df = pd.DataFrame([
        {"record_id": "1", "url": "https://a.com"},
        {"record_id": "2", "url": "https://b.com"},
    ])

    existing_df = pd.DataFrame([
        {"record_id": "1", "metadata": {"scraping": {"status": "failed"}}},
    ])

    result = pipeline._select_records_to_scrape(
        input_df=input_df,
        existing_df=existing_df,
        retry_failed=False,
    )

    assert result["record_id"].tolist() == ["2"]


def test_merge_record_prefers_scraped_published_at(storage, paths):
    pipeline = ScrapingPipeline(storage=storage, paths=paths)

    row = pipeline._merge_record_and_scrape_result(
        record_dict={
            "record_id": "1",
            "url": "https://example.com",
            "published_at": "2026-01-01T00:00:00Z",
            "metadata": {"source_common_name": "example.com"},
        },
        scrape_result={
            "title": " Title ",
            "text": " Body ",
            "published_at": "2026-01-01T12:34:00Z",
            "metadata": {
                "scraping": {"status": "success"},
                "published_at": {
                    "source": "page_metadata",
                    "precision": "second",
                },
            },
        },
    )

    assert row["published_at"] == "2026-01-01T12:34:00Z"
    assert row["metadata"]["published_at"] == {
        "source": "page_metadata",
        "precision": "second",
    }


def test_merge_record_keeps_original_published_at_when_scraped_missing(storage, paths):
    pipeline = ScrapingPipeline(storage=storage, paths=paths)

    row = pipeline._merge_record_and_scrape_result(
        record_dict={
            "record_id": "gdelt-1",
            "url": "https://example.com/article",
            "published_at": "2026-06-24T12:00:00Z",
            "metadata": {"source_common_name": "example.com"},
        },
        scrape_result={
            "title": "Storm causes outage",
            "text": "Thousands lost power.",
            "published_at": None,
            "metadata": {
                "scraping": {"status": "success"},
                "published_at": {
                    "source": None,
                    "precision": None,
                },
            },
        },
    )

    assert row["published_at"] == "2026-06-24T12:00:00Z"
    assert row["metadata"]["published_at"] == {
        "source": "gdelt",
        "precision": "15min",
    }


def test_clean_only_cleans_successful_records(storage, paths):
    pipeline = ScrapingPipeline(storage=storage, paths=paths)

    success = pipeline._clean_scraped_record({
        "title": "  Hello\n\nWorld ",
        "text": "  This   is\ntext ",
        "metadata": {"scraping": {"status": "success"}},
    })

    failed = pipeline._clean_scraped_record({
        "title": "  Bad\nTitle ",
        "text": "",
        "metadata": {"scraping": {"status": "failed"}},
    })

    assert success["title"] 
    assert success["text_length"] == len(success["text"])
    assert success["metadata"]["scraping"]["status"] == "success"

    assert failed["title"] == "  Bad\nTitle "
    assert failed["text_length"] == 0


def test_merge_scraped_results_keeps_latest_record_id(storage, paths):
    pipeline = ScrapingPipeline(storage=storage, paths=paths)

    existing_df = pd.DataFrame([
        {"record_id": "1", "metadata": {"scraping": {"status": "failed"}}},
        {"record_id": "2", "metadata": {"scraping": {"status": "success"}}},
    ])

    scraped_df = pd.DataFrame([
        {"record_id": "1", "metadata": {"scraping": {"status": "success"}}},
    ])

    result = pipeline._merge_scraped_results(existing_df, scraped_df)

    assert len(result) == 2

    row = result[result["record_id"] == "1"].iloc[0]
    assert row["metadata"]["scraping"]["status"] == "success"