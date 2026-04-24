import io
import mimetypes
import uuid

from miniopy_async import Minio

from app.config import settings

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_MAGIC = {
    b"\xff\xd8\xff",           # JPEG
    b"\x89PNG\r\n\x1a\n",     # PNG
    b"RIFF",                   # WEBP (starts with RIFF....WEBP)
}

_minio: Minio | None = None
_public_minio: Minio | None = None


def get_minio() -> Minio:
    global _minio
    if _minio is None:
        _minio = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _minio


def get_public_minio() -> Minio:
    global _public_minio
    if _public_minio is None:
        public_endpoint = settings.minio_public_endpoint or settings.minio_endpoint
        _public_minio = Minio(
            public_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _public_minio


def build_public_photo_url(key: str) -> str:
    endpoint = settings.minio_public_endpoint or settings.minio_endpoint
    scheme = "https" if settings.minio_secure else "http"
    return f"{scheme}://{endpoint}/{settings.minio_bucket}/{key}"


def validate_image(data: bytes, content_type: str) -> None:
    """Validate MIME type and magic bytes to prevent polyglot uploads."""
    if content_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Unsupported content type: {content_type}")
    header = data[:8]
    valid = any(header.startswith(magic) for magic in ALLOWED_MAGIC)
    if not valid:
        raise ValueError("File content does not match a valid image format")


async def upload_photo(data: bytes, content_type: str, user_id: str) -> str:
    """Upload photo to MinIO and return the storage key."""
    validate_image(data, content_type)
    ext = mimetypes.guess_extension(content_type) or ".jpg"
    key = f"photos/{user_id}/{uuid.uuid4()}{ext}"
    client = get_minio()
    await client.put_object(
        settings.minio_bucket,
        key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return key


async def get_presigned_url(key: str, expires: int = 3600) -> str:
    """Return browser-facing photo URL for the given storage key."""
    if settings.minio_bucket_public:
        return build_public_photo_url(key)

    # Private bucket mode: return pre-signed GET URL.
    from datetime import timedelta
    client = get_public_minio()
    url = await client.presigned_get_object(
        settings.minio_bucket, key, expires=timedelta(seconds=expires)
    )
    return url
