from __future__ import annotations


from pathlib import Path
from typing import TypeVar


from eml_transformer.logging import get_logger
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.config.loader import StorageConfig

from eml_transformer.storage.base import Storage
from eml_transformer.storage.local import LocalStorage
from eml_transformer.storage.s3 import S3Storage
from eml_transformer.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def make_storage(
    config: StorageConfig,
    *,
    paths: StoragePaths,
) -> Storage:
    backend = config.backend.strip().lower()

    if backend == "local":
        return LocalStorage(
            paths=paths,
            base_dir=Path(config.root),
        )

    if backend == "s3":
        return S3Storage(
            paths=paths,
            bucket=config.bucket,
            prefix=config.prefix,
            region=config.region,
            profile=config.profile,
            endpoint_url=config.endpoint_url,
        )

    raise ValueError(
        f"Unsupported storage backend: {config.backend!r}"
    )