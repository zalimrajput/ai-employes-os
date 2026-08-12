"""Diagnose refresh-token capability + OneDrive 404 for the technove org."""
import sys

sys.path.insert(0, ".")

import httpx

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.integration import Integration
from app.utils.encryption import decrypt_value

ORG = "88f45e8f-73f3-4b9a-b247-a1c826c08311"


def row(db, provider):
    return (
        db.query(Integration)
        .filter(Integration.organization_id == ORG, Integration.provider == provider)
        .first()
    )


def main():
    db = SessionLocal()
    try:
        print("--- refresh capability (rows WITH a stored refresh token) ---")
        for p, url in [
            ("google-sheets", "https://oauth2.googleapis.com/token"),
            ("onedrive", "https://login.microsoftonline.com/common/oauth2/v2.0/token"),
            ("xero", "https://identity.xero.com/connect/token"),
        ]:
            r = row(db, p)
            rt = decrypt_value(r.refresh_token) if r and r.refresh_token else None
            if not rt:
                print(f"{p:14s} no refresh token stored")
                continue
            data = {"grant_type": "refresh_token", "refresh_token": rt}
            kwargs = {}
            if p == "google-sheets":
                data["client_id"] = settings.GMAIL_CLIENT_ID
                data["client_secret"] = settings.GMAIL_CLIENT_SECRET
            elif p == "onedrive":
                data["client_id"] = settings.MICROSOFT_CLIENT_ID
                data["client_secret"] = settings.MICROSOFT_CLIENT_SECRET
            else:  # xero uses HTTP Basic
                kwargs["auth"] = (settings.XERO_CLIENT_ID, settings.XERO_CLIENT_SECRET)
            try:
                resp = httpx.post(url, data=data, timeout=30, **kwargs)
            except httpx.HTTPError as exc:
                print(f"{p:14s} refresh ERROR {type(exc).__name__}")
                continue
            body = resp.text[:120].replace("\n", " ")
            try:
                has_at = bool(resp.json().get("access_token"))
            except ValueError:
                has_at = False
            if resp.status_code < 300 and has_at:
                print(f"{p:14s} refresh OK (token rotates)")
            else:
                print(f"{p:14s} refresh FAIL {resp.status_code}: {body}")

        print()
        print("--- OneDrive 404 diagnosis (probe /me/drive metadata) ---")
        r = row(db, "onedrive")
        tok = decrypt_value(r.access_token)
        for path in ("https://graph.microsoft.com/v1.0/me/drive", "https://graph.microsoft.com/v1.0/me"):
            try:
                resp = httpx.get(path, headers={"Authorization": f"Bearer {tok}"}, timeout=15)
                body = resp.text[:160].replace(chr(10), " ")
                print(f"{path.split('/v1.0/')[-1]:20s} -> {resp.status_code} {body}")
            except httpx.HTTPError as exc:
                print(f"{path.split('/v1.0/')[-1]:20s} -> ERROR {type(exc).__name__}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
