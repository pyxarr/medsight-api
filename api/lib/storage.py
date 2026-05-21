import os
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4

import requests


SUPABASE_BATCH_BUCKET = "assessment-batches"
SUPABASE_COMMUNITY_BUCKET = "community-media"


def build_batch_storage_path(clinician_user_id: str, original_filename: str) -> str:
    """Return a unique Supabase Storage path for one uploaded batch file."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_filename = original_filename.replace(" ", "_")
    return f"clinicians/{clinician_user_id}/{timestamp}-{uuid4()}-{safe_filename}"


def upload_batch_file(file_bytes: bytes, storage_path: str, content_type: str = "text/csv") -> str:
    """Upload one batch file to Supabase Storage and return the stored path."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_secret_key = os.getenv("SUPABASE_SECRET_KEY")

    if not supabase_url or not supabase_secret_key:
        raise RuntimeError("Supabase Storage is not configured.")

    upload_url = f"{supabase_url.rstrip('/')}/storage/v1/object/{SUPABASE_BATCH_BUCKET}/{storage_path}"
    response = requests.post(
        upload_url,
        headers={
            "apikey": supabase_secret_key,
            "Authorization": f"Bearer {supabase_secret_key}",
            "Content-Type": content_type,
            "x-upsert": "true",
        },
        data=file_bytes,
        timeout=30,
    )

    if response.status_code >= 400:
        raise RuntimeError(f"Batch file could not be uploaded to Supabase Storage. Status: {response.status_code}")

    return storage_path


def build_community_media_path(user_id: str, original_filename: str) -> str:
    """Return a unique Supabase Storage path for one uploaded community media file."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_filename = original_filename.replace(" ", "_")
    return f"posts/{user_id}/{timestamp}-{uuid4()}-{safe_filename}"


def upload_community_media(file_bytes: bytes, storage_path: str, content_type: str = "application/octet-stream") -> str:
    """Upload one community media file to Supabase Storage and return the stored path."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_secret_key = os.getenv("SUPABASE_SECRET_KEY")

    if not supabase_url or not supabase_secret_key:
        raise RuntimeError("Supabase Storage is not configured.")

    upload_url = f"{supabase_url.rstrip('/')}/storage/v1/object/{SUPABASE_COMMUNITY_BUCKET}/{storage_path}"
    response = requests.post(
        upload_url,
        headers={
            "apikey": supabase_secret_key,
            "Authorization": f"Bearer {supabase_secret_key}",
            "Content-Type": content_type,
            "x-upsert": "true",
        },
        data=file_bytes,
        timeout=30,
    )

    if response.status_code >= 400:
        raise RuntimeError(f"Community media could not be uploaded to Supabase Storage. Status: {response.status_code}")

    return storage_path


def get_public_media_url(storage_path: str) -> str:
    """Return the public Supabase Storage URL for one community media file."""
    supabase_url = os.getenv("SUPABASE_URL")
    if not supabase_url:
        raise RuntimeError("Supabase URL is not configured.")

    return f"{supabase_url.rstrip('/')}/storage/v1/object/public/{SUPABASE_COMMUNITY_BUCKET}/{storage_path}"


def delete_community_media(storage_path: str) -> None:
    """Delete one community media file from Supabase Storage."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_secret_key = os.getenv("SUPABASE_SECRET_KEY")

    if not supabase_url or not supabase_secret_key:
        raise RuntimeError("Supabase Storage is not configured.")

    delete_url = f"{supabase_url.rstrip('/')}/storage/v1/object/{SUPABASE_COMMUNITY_BUCKET}/{storage_path}"
    response = requests.delete(
        delete_url,
        headers={
            "apikey": supabase_secret_key,
            "Authorization": f"Bearer {supabase_secret_key}",
        },
        timeout=30,
    )

    if response.status_code >= 400:
        raise RuntimeError(f"Community media could not be deleted from Supabase Storage. Status: {response.status_code}")


def extract_storage_path_from_url(public_url: str) -> str | None:
    """Extract the storage path from a Supabase public media URL."""
    parsed = urlparse(public_url)
    prefix = f"/storage/v1/object/public/{SUPABASE_COMMUNITY_BUCKET}/"
    if parsed.path.startswith(prefix):
        return parsed.path[len(prefix):]
    return None
