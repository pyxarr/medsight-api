import os
from datetime import datetime, timezone
from uuid import uuid4

import requests


SUPABASE_BATCH_BUCKET = "assessment-batches"


def build_batch_storage_path(clinician_user_id: str, original_filename: str) -> str:
    """Return a unique Supabase Storage path for one uploaded batch CSV."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_filename = original_filename.replace(" ", "_")
    return f"clinicians/{clinician_user_id}/{timestamp}-{uuid4()}-{safe_filename}"


def upload_batch_csv(file_bytes: bytes, storage_path: str) -> str:
    """Upload one batch CSV to Supabase Storage and return the stored path."""
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
            "Content-Type": "text/csv",
            "x-upsert": "true",
        },
        data=file_bytes,
        timeout=30,
    )

    if response.status_code >= 400:
        raise RuntimeError("Batch CSV could not be uploaded to Supabase Storage.")

    return storage_path
