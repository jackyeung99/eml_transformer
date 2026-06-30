import pandas as pd

from eml_transformer.pipelines.embedding_pipeline import EmbeddingPipeline


def test_run_source_reads_input_from_storage(storage, paths, embedding_model):
    source = "gdelt"
    model_name = "fake-model"

    input_df = pd.DataFrame(
        [
            {
                "record_id": "r1",
                "title": "Storm warning",
                "text": "High winds expected.",
                "published_at": "2026-01-01T00:00:00Z",
            }
        ]
    )

    storage.write_parquet(
        input_df,
        paths.silver_records(source=source, name="records"),
    )

    pipeline = EmbeddingPipeline(
        storage=storage,
        paths=paths,
        embedder=embedding_model,
    )

    result = pipeline.run_source(
        source=source,
        embedding_config={
            "model": model_name,
            "embedding_batch_size": 8,
            "save_batch_size": 1000,
        },
        source_config={
            "embedding_input": "records",
        },
    )

    assert result.status == "success", result.error
    assert result.records_read == 1
    assert result.embeddings_created == 1
    assert result.embeddings_skipped == 0

    output = storage.read_parquet(result.output_key)

    assert len(output) == 1
    assert output.loc[0, "record_id"] == "r1"
    assert output.loc[0, "embedding_text"] == (
        "Storm warning\n\nHigh winds expected."
    )
    assert output.loc[0, "embedding"] == [0.1, 0.2, 0.3]


def test_skip_seen_embedding(storage, paths, embedding_model):
    source = "gdelt"
    model_name = "fake-model"

    input_df = pd.DataFrame(
        [
            {
                "record_id": "r1",
                "title": "Storm warning",
                "text": "High winds expected.",
                "published_at": "2026-01-01T00:00:00Z",
            }
        ]
    )

    existing_df = pd.DataFrame(
        [
            {
                "record_id": "r1",
                "title": "Storm warning",
                "text": "High winds expected.",
                "embedding_text": "Storm warning\n\nHigh winds expected.",
                "published_at": "2026-01-01T00:00:00Z",
                "embedding": [0.1, 0.2, 0.3],
                "embedding_model": model_name,
                "embedding_input_type": "passage",
                "source": source,
            }
        ]
    )

    storage.write_parquet(
        input_df,
        paths.silver_records(source=source, name="records"),
    )

    output_key = paths.gold_records(
        source=source,
        model_name=model_name,
    )

    storage.write_parquet(existing_df, output_key)

    pipeline = EmbeddingPipeline(
        storage=storage,
        paths=paths,
        embedder=embedding_model,
    )

    result = pipeline.run_source(
        source=source,
        embedding_config={
            "model": model_name,
            "embedding_batch_size": 8,
            "save_batch_size": 1000,
        },
        source_config={
            "embedding_input": "records",
        },
    )

    assert result.status == "up_to_date"
    assert result.records_read == 1
    assert result.embeddings_created == 0
    assert result.embeddings_skipped == 1
    assert result.output_key == output_key

    output = storage.read_parquet(result.output_key)

    assert len(output) == 1
    assert output.loc[0, "record_id"] == "r1"
    assert output.loc[0, "embedding_text"] == (
        "Storm warning\n\nHigh winds expected."
    )
    assert output.loc[0, "embedding"] == [0.1, 0.2, 0.3]


def test_skips_invalid_embedding_text(storage, paths, embedding_model):
    source = "gdelt"
    model_name = "fake-model"

    input_df = pd.DataFrame(
        [
            {
                "record_id": "r1",
                "title": "",
                "text": "",
                "published_at": "2026-01-01T00:00:00Z",
            },
            {
                "record_id": "r2",
                "title": "Valid title",
                "text": "",
                "published_at": "2026-01-02T00:00:00Z",
            },
        ]
    )

    storage.write_parquet(
        input_df,
        paths.silver_records(source=source, name="records"),
    )

    pipeline = EmbeddingPipeline(
        storage=storage,
        paths=paths,
        embedder=embedding_model,
    )

    result = pipeline.run_source(
        source=source,
        embedding_config={
            "model": model_name,
            "embedding_batch_size": 8,
            "save_batch_size": 1000,
        },
        source_config={
            "embedding_input": "records",
        },
    )

    assert result.status == "success", result.error
    assert result.records_read == 2
    assert result.embeddings_created == 1
    assert result.embeddings_skipped == 1

    output = storage.read_parquet(result.output_key)

    assert len(output) == 1
    assert output.loc[0, "record_id"] == "r2"
    assert output.loc[0, "embedding_text"] == "Valid title"


def test_no_valid_text_returns_no_valid_text(storage, paths, embedding_model):
    source = "gdelt"
    model_name = "fake-model"

    input_df = pd.DataFrame(
        [
            {
                "record_id": "r1",
                "title": "",
                "text": "",
                "published_at": "2026-01-01T00:00:00Z",
            }
        ]
    )

    storage.write_parquet(
        input_df,
        paths.silver_records(source=source, name="records"),
    )

    pipeline = EmbeddingPipeline(
        storage=storage,
        paths=paths,
        embedder=embedding_model,
    )

    result = pipeline.run_source(
        source=source,
        embedding_config={
            "model": model_name,
            "embedding_batch_size": 8,
            "save_batch_size": 1000,
        },
        source_config={
            "embedding_input": "records",
        },
    )

    assert result.status == "no_valid_text"
    assert result.records_read == 1
    assert result.embeddings_created == 0
    assert result.embeddings_skipped == 1


def test_periodically_saves_embeddings(storage, paths, embedding_model):
    source = "gdelt"
    model_name = "fake-model"

    input_df = pd.DataFrame(
        [
            {
                "record_id": "r1",
                "title": "Title 1",
                "text": "Text 1",
                "published_at": "2026-01-01T00:00:00Z",
            },
            {
                "record_id": "r2",
                "title": "Title 2",
                "text": "Text 2",
                "published_at": "2026-01-02T00:00:00Z",
            },
            {
                "record_id": "r3",
                "title": "Title 3",
                "text": "Text 3",
                "published_at": "2026-01-03T00:00:00Z",
            },
        ]
    )

    storage.write_parquet(
        input_df,
        paths.silver_records(source=source, name="records"),
    )

    pipeline = EmbeddingPipeline(
        storage=storage,
        paths=paths,
        embedder=embedding_model,
    )

    result = pipeline.run_source(
        source=source,
        embedding_config={
            "model": model_name,
            "embedding_batch_size": 2,
            "save_batch_size": 1,
        },
        source_config={
            "embedding_input": "records",
        },
    )

    assert result.status == "success", result.error
    assert result.records_read == 3
    assert result.embeddings_created == 3
    assert result.embeddings_skipped == 0

    output = storage.read_parquet(result.output_key)

    assert len(output) == 3
    assert output["record_id"].tolist() == ["r1", "r2", "r3"]
    assert output["embedding"].tolist() == [
        [0.1, 0.2, 0.3],
        [0.1, 0.2, 0.3],
        [0.1, 0.2, 0.3],
    ]


def test_embedding_batch_size_is_passed_to_embedder(storage, paths, embedding_model):
    source = "gdelt"
    model_name = "fake-model"

    input_df = pd.DataFrame(
        [
            {
                "record_id": "r1",
                "title": "Title 1",
                "text": "Text 1",
                "published_at": "2026-01-01T00:00:00Z",
            },
            {
                "record_id": "r2",
                "title": "Title 2",
                "text": "Text 2",
                "published_at": "2026-01-02T00:00:00Z",
            },
        ]
    )

    storage.write_parquet(
        input_df,
        paths.silver_records(source=source, name="records"),
    )

    pipeline = EmbeddingPipeline(
        storage=storage,
        paths=paths,
        embedder=embedding_model,
    )

    result = pipeline.run_source(
        source=source,
        embedding_config={
            "model": model_name,
            "embedding_batch_size": 16,
            "save_batch_size": 1000,
        },
        source_config={
            "embedding_input": "records",
        },
    )

    assert result.status == "success", result.error

    assert embedding_model.calls == [
        {
            "texts": [
                "Title 1\n\nText 1",
                "Title 2\n\nText 2",
            ],
            "batch_size": 16,
        }
    ]