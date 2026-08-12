"""S3-compatible cloud storage (AWS S3 / Cloudflare R2) via httpx + SigV4.

No ``boto3`` dependency: AWS Signature V4 is implemented directly, so both
AWS S3 and Cloudflare R2 (and any other S3-compatible endpoint) work through
the same client. Uploads are ``PUT`` requests signed with the access key.
"""
import hashlib
import hmac
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit

import httpx


class CloudStorageError(Exception):
    """Raised when the storage provider rejects a request."""


def _hmac_sha256(key: bytes, msg: bytes) -> bytes:
    return hmac.new(key, msg, hashlib.sha256).digest()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sign_v4(
    *,
    method: str,
    url: str,
    payload: bytes,
    extra_headers: dict,
    access_key_id: str,
    secret_access_key: str,
    region: str,
    service: str,
    now: datetime,
) -> dict:
    """Return the SigV4 Authorization header + amz headers for a request."""
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    payload_hash = _sha256_hex(payload)

    parsed = urlsplit(url)
    headers = {
        "host": parsed.netloc,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
        **{k.lower(): str(v) for k, v in extra_headers.items()},
    }
    # Canonical headers must be sorted by lower-cased name.
    canonical_headers = "".join(f"{k}:{v}\n" for k, v in sorted(headers.items()))
    signed_headers = ";".join(sorted(headers))

    canonical_uri = parsed.path or "/"
    canonical_query = parsed.query or ""
    canonical_request = "\n".join(
        [
            method.upper(),
            canonical_uri,
            canonical_query,
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            _sha256_hex(canonical_request.encode("utf-8")),
        ]
    )
    k_date = _hmac_sha256(("AWS4" + secret_access_key).encode("utf-8"), date_stamp.encode("utf-8"))
    k_region = _hmac_sha256(k_date, region.encode("utf-8"))
    k_service = _hmac_sha256(k_region, service.encode("utf-8"))
    k_signing = _hmac_sha256(k_service, b"aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key_id}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {"Authorization": authorization, "x-amz-date": amz_date, "x-amz-content-sha256": payload_hash}


def _quote_key(key: str) -> str:
    return "/".join(quote(part, safe="") for part in key.split("/"))


class CloudStorageClient:
    """S3-compatible object storage client (path-style URLs)."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        region: str = "auto",
    ):
        self._endpoint = endpoint_url.rstrip("/")
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._bucket = bucket
        self._region = region or "auto"

    def _object_url(self, key: str) -> str:
        return f"{self._endpoint}/{self._bucket}/{_quote_key(key)}"

    def _signed_headers(self, method: str, url: str, payload: bytes) -> dict:
        return _sign_v4(
            method=method,
            url=url,
            payload=payload,
            extra_headers={},
            access_key_id=self._access_key_id,
            secret_access_key=self._secret_access_key,
            region=self._region,
            service="s3",
            now=datetime.now(timezone.utc),
        )

    def check_connection(self) -> None:
        """Verify the bucket is reachable with the configured credentials.

        Raises ``CloudStorageError`` on any failure (bad keys, wrong endpoint,
        missing bucket) so callers can surface the exact reason.
        """
        url = f"{self._endpoint}/{self._bucket}"
        headers = self._signed_headers("HEAD", url, b"")
        resp = httpx.request("HEAD", url, headers=headers, timeout=30)
        if resp.status_code >= 300:
            raise CloudStorageError(
                f"Storage check failed ({resp.status_code}): {resp.text[:200]}"
            )

    def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload bytes to the bucket; returns the object URL."""
        url = self._object_url(key)
        headers = self._signed_headers("PUT", url, data)
        headers["Content-Type"] = content_type
        resp = httpx.put(url, content=data, headers=headers, timeout=60)
        if resp.status_code >= 300:
            raise CloudStorageError(
                f"Storage PUT failed ({resp.status_code}): {resp.text[:200]}"
            )
        return url

    def get_object(self, key: str) -> bytes:
        """Download bytes from the bucket."""
        url = self._object_url(key)
        headers = self._signed_headers("GET", url, b"")
        resp = httpx.get(url, headers=headers, timeout=60)
        if resp.status_code >= 300:
            raise CloudStorageError(
                f"Storage GET failed ({resp.status_code}): {resp.text[:200]}"
            )
        return resp.content

    def delete_object(self, key: str) -> bool:
        """Delete an object from the bucket."""
        url = self._object_url(key)
        headers = self._signed_headers("DELETE", url, b"")
        resp = httpx.request("DELETE", url, headers=headers, timeout=60)
        return resp.status_code < 300


def get_client() -> CloudStorageClient | None:
    """Return a configured CloudStorageClient, or None when unconfigured.

    Reads ``STORAGE_PROVIDER`` (s3|r2), ``S3_ENDPOINT_URL``,
    ``S3_ACCESS_KEY_ID``, ``S3_SECRET_ACCESS_KEY``, ``S3_BUCKET`` and
    ``S3_REGION`` from settings.
    """
    from app.core.config import settings

    if settings.STORAGE_PROVIDER not in ("s3", "r2"):
        return None
    if not (settings.S3_ENDPOINT_URL and settings.S3_ACCESS_KEY_ID and settings.S3_BUCKET):
        return None
    return CloudStorageClient(
        endpoint_url=settings.S3_ENDPOINT_URL,
        access_key_id=settings.S3_ACCESS_KEY_ID,
        secret_access_key=settings.S3_SECRET_ACCESS_KEY or "",
        bucket=settings.S3_BUCKET,
        region=settings.S3_REGION,
    )
