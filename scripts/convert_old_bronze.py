from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eml_transformer.sources.registry import create_source
from eml_transformer.ingestion.orchestrator import IngestionPipeline
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.base import LocalStorage


def migrate_jsonl(
    source_name: str,
    input_path: Path,
    output_path: Path,
    source_config: dict[str, Any] | None = None,
) -> None:
    source = create_source(
        source_name,
        **(source_config or {}),
    )

    old_records: list[dict[str, Any]] = []

    with input_path.open("r", encoding="utf-8") as src:
        for line_number, line in enumerate(src, start=1):
            if not line.strip():
                continue

            try:
                old_record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number}"
                ) from exc

            # Handles both old raw records and records already using
            # an envelope containing a `raw` field.
            old_records.append(
                old_record.get("raw", old_record)
            )

    bronze_records = source._build_bronze_records(old_records)

    seen_ids: set[str] = set()
    records_written = 0
    duplicates_skipped = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as dst:
        for record in bronze_records:
            if record.record_id in seen_ids:
                duplicates_skipped += 1
                continue

            seen_ids.add(record.record_id)
            dst.write(
                json.dumps(
                    record.to_dict(),
                    default=str,
                )
                + "\n"
            )
            records_written += 1

    # Rebuild the pipeline dedupe state from the migrated records.
    storage = LocalStorage(base_dir=Path("."))
    paths = StoragePaths()
    pipeline = IngestionPipeline(
        storage=storage,
        paths=paths,
    )

    dedupe_key = paths.dedupe_state(source_name)
    pipeline._save_seen(
        key=dedupe_key,
        seen=seen_ids,
    )

    print(f"Source: {source_name}")
    print(f"Original records: {len(old_records)}")
    print(f"Bronze records written: {records_written}")
    print(f"Duplicates removed: {duplicates_skipped}")
    print(f"Dedupe IDs saved: {len(seen_ids)}")
    print(f"Output saved to: {output_path}")


if __name__ == "__main__":
    source_name = "miso_notifications"
    directory = Path(
        f"data/bronze/source={source_name}"
    )

    migrate_jsonl(
        source_name=source_name,
        input_path=directory / "records_old.jsonl",
        output_path=directory / "records.jsonl",
    )