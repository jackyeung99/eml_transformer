import pandas as pd

from eml_transformer.embeddings.pipeline import EmbeddingPipeline


def make_embedding_config(
    source: str,
    *,
    embedding_batch_size: int = 8,
) -> dict:
    return {
        "input": f"silver:{source}:records",
        "output": f"gold:{source}:embeddings",
        "write_mode": "append",
        "embedding_batch_size": embedding_batch_size,
        "text_columns": [
            "title",
            "text",
        ],
    }


def test_run_source_reads_input_from_storage(
    storage,
    paths,
    embedding_model,
):
    source = "gdelt"
    embedding_config = make_embedding_config(source)

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
        paths.dataset(embedding_config["input"]),
    )

    pipeline = EmbeddingPipeline(
        storage=storage,
        paths=paths,
        embedder=embedding_model,
    )

    result = pipeline.run_source(
        source_name=source,
        embedding_config=embedding_config,
    )

    expected_output_key = paths.dataset(
        embedding_config["output"]
    )

    assert result.status == "success", result.error
    assert result.records_read == 1
    assert result.embeddings_created == 1
    assert result.embeddings_skipped == 0
    assert result.output_key == expected_output_key

    output = storage.read_parquet(expected_output_key)

    assert len(output) == 1
    assert output.loc[0, "record_id"] == "r1"
    assert output.loc[0, "embedding_text"] == (
        "Storm warning\n\nHigh winds expected."
    )
    assert output.loc[0, "embedding"] == [0.1, 0.2, 0.3]

def test_skip_seen_embedding(
    storage,
    paths,
    embedding_model,
):
    source = "gdelt"
    embedding_config = make_embedding_config(source)

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
                "embedding_text": (
                    "Storm warning\n\nHigh winds expected."
                ),
                "published_at": "2026-01-01T00:00:00Z",
                "embedding": [0.1, 0.2, 0.3],
                "embedding_model": "fake-model",
                "embedding_input_type": "passage",
                "source": source,
            }
        ]
    )

    input_key = paths.dataset(
        embedding_config["input"]
    )
    output_key = paths.dataset(
        embedding_config["output"]
    )

    storage.write_parquet(input_df, input_key)
    storage.write_parquet(existing_df, output_key)

    pipeline = EmbeddingPipeline(
        storage=storage,
        paths=paths,
        embedder=embedding_model,
    )

    result = pipeline.run_source(
        source_name=source,
        embedding_config=embedding_config,
    )

    assert result.status == "up_to_date"
    assert result.records_read == 1
    assert result.embeddings_created == 0
    assert result.embeddings_skipped == 1
    assert result.output_key == output_key

    output = storage.read_parquet(output_key)

    assert len(output) == 1
    assert output.loc[0, "record_id"] == "r1"