"""Storage: record file metadata and keep per-org storage usage in sync."""
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.storage import StorageFile, StorageQuota

logger = logging.getLogger("app.services.storage_service")


def get_or_create_quota(db: Session, organization_id) -> StorageQuota:
    quota = (
        db.query(StorageQuota)
        .filter(StorageQuota.organization_id == organization_id)
        .first()
    )
    if quota is None:
        quota = StorageQuota(organization_id=organization_id)
        db.add(quota)
        db.commit()
        db.refresh(quota)
    return quota


def register_file(
    db: Session,
    organization_id,
    uploaded_by,
    file_name: str,
    file_path: str,
    mime_type: str | None = None,
    file_size: int = 0,
    bucket: str = "documents",
    entity_type: str | None = None,
    entity_id=None,
    metadata: dict | None = None,
) -> StorageFile:
    row = StorageFile(
        organization_id=organization_id,
        uploaded_by=uploaded_by,
        file_name=file_name,
        file_path=file_path,
        mime_type=mime_type,
        file_size=file_size,
        bucket=bucket,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata or {},
    )
    db.add(row)
    quota = get_or_create_quota(db, organization_id)
    quota.used_storage_bytes = (quota.used_storage_bytes or 0) + file_size
    db.commit()
    db.refresh(row)
    return row


def delete_file(db: Session, file: StorageFile) -> None:
    quota = get_or_create_quota(db, file.organization_id)
    quota.used_storage_bytes = max(
        (quota.used_storage_bytes or 0) - (file.file_size or 0), 0
    )
    db.delete(file)
    db.commit()


def _generated_documents_dir():
    """The local directory where generated files are cached for /documents/."""
    return Path(__file__).resolve().parent.parent / "generated_documents"


def save_blob(
    db: Session,
    organization_id,
    filename: str,
    data: bytes,
    mime_type: str | None = None,
    subdir: str = "",
    uploaded_by=None,
    entity_type: str | None = None,
    entity_id=None,
    metadata: dict | None = None,
) -> dict:
    """Persist bytes to the storage backend and register the file.

    Write-through: bytes are always cached in the local generated_documents
    directory (so existing ``/documents/`` serving keeps working) and, when
    cloud storage is configured (``STORAGE_PROVIDER=s3|r2``), mirrored to the
    S3/R2 bucket. Returns the storage path used in URLs plus the provider and
    object URL. ``subdir`` is an optional bucket-like folder; the URL keeps
    the flat ``/documents/{filename}`` convention when empty.
    """
    from app.core.config import settings
    from app.integrations.cloud_storage import get_client as cloud_get_client

    out_dir = _generated_documents_dir()
    if subdir:
        out_dir = out_dir / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_bytes(data)

    storage_path = (
        f"/documents/{subdir}/{filename}" if subdir else f"/documents/{filename}"
    )
    provider = "local"
    url = None
    if settings.STORAGE_PROVIDER in ("s3", "r2"):
        client = cloud_get_client()
        if client is not None:
            try:
                key = f"{organization_id}/{subdir or 'documents'}/{filename}"
                url = client.put_object(
                    key, data, mime_type or "application/octet-stream"
                )
                provider = settings.STORAGE_PROVIDER
            except Exception as exc:  # noqa: BLE001 - never fail the caller
                logger.warning("cloud storage upload failed; kept local copy: %s", exc)

    row = register_file(
        db,
        organization_id,
        uploaded_by=uploaded_by,
        file_name=filename,
        file_path=storage_path,
        mime_type=mime_type,
        file_size=len(data),
        bucket=subdir or "documents",
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata,
    )
    if provider != "local" or url:
        row.storage_provider = provider
        row.url = url
        db.commit()
        db.refresh(row)
    return {
        "storage_path": storage_path,
        "file": str(path),
        "storage_provider": provider,
        "url": url,
        "file_id": str(row.id),
    }