"""File storage for report photos and PDFs.

``STORAGE_BACKEND=local`` keeps files on the server disk (development and free test hosting —
files disappear when such a server is rebuilt); ``s3`` uses any S3-compatible bucket
(Cloudflare R2, Backblaze B2, AWS S3, MinIO). Large files are never stored in PostgreSQL;
the database only keeps their keys.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from app.core.config import get_settings
from app.core.errors import NotFoundError


class Storage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def exists(self, key: str) -> bool: ...


def _missing(key: str) -> NotFoundError:
    return NotFoundError("FILE_NOT_FOUND", "Fayl topilmadi.", details={"key": key})


class LocalStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("invalid storage key")
        return path

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise _missing(key)
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            await asyncio.to_thread(path.unlink)

    async def exists(self, key: str) -> bool:
        return self._path(key).is_file()


class S3Storage:
    def __init__(self, *, endpoint: str, region: str, access_key: str, secret_key: str, bucket: str) -> None:
        import boto3  # imported lazily: only needed when S3 is configured

        self.bucket = bucket
        self.client: Any = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self.client.put_object, Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
        )

    async def get(self, key: str) -> bytes:
        try:
            response = await asyncio.to_thread(self.client.get_object, Bucket=self.bucket, Key=key)
        except self.client.exceptions.NoSuchKey as exc:
            raise _missing(key) from exc
        return await asyncio.to_thread(response["Body"].read)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)

    async def exists(self, key: str) -> bool:
        try:
            await asyncio.to_thread(self.client.head_object, Bucket=self.bucket, Key=key)
        except Exception:
            return False
        return True


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "s3":
        assert settings.storage_endpoint and settings.storage_bucket
        assert settings.storage_access_key and settings.storage_secret_key
        return S3Storage(
            endpoint=settings.storage_endpoint,
            region=settings.storage_region,
            access_key=settings.storage_access_key.get_secret_value(),
            secret_key=settings.storage_secret_key.get_secret_value(),
            bucket=settings.storage_bucket,
        )
    return LocalStorage(settings.storage_local_path)
