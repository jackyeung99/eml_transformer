import pandas as pd

from eml_transformer.pipelines.embedding_pipeline import EmbeddingPipeline


def test_skip_seen_embedding(storage, paths, embedding_model): 

    source = "gdelt"
    model_name = 'fake_model'

    # input
    input_key = paths.silver_records(
        source=source,
        name="records",
    )

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

    storage.write_parquet(input_df, input_key)

    # output
    output_key = paths.gold_records(
        model_name= model_name,
        source=source
    )

    existing_df = pd.DataFrame(
        [
            {
                "record_id": "r1",
                "title": "Storm warning",
                "embedding_text": "Storm warning\n\nHigh winds expected.",
                "published_at": "2026-01-01T00:00:00Z",
                "embedding": [0.1, 0.2, 0.3]
            }
        ]
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
        },
        source_config={
            "embedding_input": "records",
        },
    )
    
    output = storage.read_parquet(result.output_key)

    assert result.status == "up_to_date"
    assert result.records_read == 1
    assert result.embeddings_created == 0
    assert result.embeddings_skipped == 1

    assert len(output) == 1
    assert output.loc[0, "record_id"] == "r1"
    assert output.loc[0, "embedding_text"] == "Storm warning\n\nHigh winds expected."
    assert output.loc[0, "embedding"] == [0.1, 0.2, 0.3]

def test_run_source_reads_input_from_storage(storage, paths, embedding_model):
    source = "gdelt"

    input_key = paths.silver_records(
        source=source,
        name="records",
    )

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

    storage.write_parquet(input_df, input_key)
    
    input_key = paths.silver_records(
        source=source,
        name="records",
    )

 
    pipeline = EmbeddingPipeline(
        storage=storage,
        paths=paths,
        embedder=embedding_model,
    )

    result = pipeline.run_source(
        source=source,
        embedding_config={
            "model": "fake-model",
        },
        source_config={
            "embedding_input": "records",
        },
    )

    output = storage.read_parquet(result.output_key)

    assert result.status == "success"
    assert result.records_read == 1
    assert result.embeddings_created == 1

    assert len(output) == 1
    assert output.loc[0, "record_id"] == "r1"
    assert output.loc[0, "embedding_text"] == "Storm warning\n\nHigh winds expected."
    assert output.loc[0, "embedding"] == [0.1, 0.2, 0.3]