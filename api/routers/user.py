import logging
import os

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.repositories.user_repository import UserRepository
from api.db.session import get_db
from api.lib.auth import CurrentUser, get_current_user
from api.schemas.user import UserProfileResponse, ClinicianProfileUpdate

LOGGER = logging.getLogger(__name__)

router = APIRouter()

MAX_LICENCE_DOCUMENT_SIZE_BYTES = 5 * 1024 * 1024

SUPABASE_LICENCE_DOCUMENTS_BUCKET = "licence-documents"

MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024

SUPABASE_AVATARS_BUCKET = "avatars"


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Return the current product user profile and bootstrap it when missing."""
    user_repository = UserRepository()

    try:
        user_record = await user_repository.get_or_create_from_auth_user(
            database_session=database_session,
            current_user=current_user,
        )
    except Exception:
        LOGGER.exception(
            "Failed to load or create product user profile for user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "User profile could not be loaded. Please try again or contact support "
                "if the problem persists."
            ),
        )

    return UserProfileResponse.model_validate(user_record)


@router.patch("/me", response_model=UserProfileResponse)
async def patch_current_user_profile(
    request: ClinicianProfileUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Update clinician profile fields (partial update)."""
    user_repository = UserRepository()

    try:
        updated_user = await user_repository.update_profile(
            database_session=database_session,
            current_user=current_user,
            institution=request.institution,
            specialisation=request.specialisation,
            experience_years=request.experience_years,
            location=request.location,
        )
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.exception(
            "Failed to update user profile for user_id=%s. Error: %s",
            current_user.id,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User profile could not be updated. Please try again or contact support "
            "if the problem persists.",
        )

    if updated_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return UserProfileResponse.model_validate(updated_user)


@router.patch("/me/verification", response_model=UserProfileResponse)
async def submit_clinician_verification(
    medical_licence_number: str = Form(...),
    file: UploadFile | None = File(None),
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Submit a clinician licence number and an optional licence document."""
    licence_document_url = None
    if file is not None:
        file_bytes = await file.read()
        if len(file_bytes) > MAX_LICENCE_DOCUMENT_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Licence document exceeds the 5MB size limit.",
            )

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_secret_key = os.getenv("SUPABASE_SECRET_KEY")
        if not supabase_url or not supabase_secret_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Licence document upload failed.",
            )

        storage_path = f"{current_user.id}/{file.filename}"
        upload_url = (
            f"{supabase_url.rstrip('/')}/storage/v1/object/"
            f"{SUPABASE_LICENCE_DOCUMENTS_BUCKET}/{storage_path}"
        )
        upload_response = httpx.post(
            upload_url,
            headers={
                "apikey": supabase_secret_key,
                "Authorization": f"Bearer {supabase_secret_key}",
                "Content-Type": file.content_type or "application/octet-stream",
                "x-upsert": "true",
            },
            content=file_bytes,
            timeout=30,
        )
        if upload_response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Licence document upload failed.",
            )

        licence_document_url = (
            f"{supabase_url.rstrip('/')}/storage/v1/object/public/"
            f"{SUPABASE_LICENCE_DOCUMENTS_BUCKET}/{current_user.id}/{file.filename}"
        )

    user_repository = UserRepository()
    try:
        updated_user = await user_repository.submit_verification(
            database_session=database_session,
            user_id=current_user.id,
            medical_licence_number=medical_licence_number,
            licence_document_url=licence_document_url,
        )
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception(
            "Failed to submit verification for user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Verification could not be saved. Please try again or contact "
                "support if the problem persists."
            ),
        )

    return UserProfileResponse.model_validate(updated_user)


@router.patch("/me/avatar", response_model=UserProfileResponse)
async def update_current_user_avatar(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Upload an avatar image for the current user and persist its URL."""
    file_bytes = await file.read()
    if len(file_bytes) > MAX_AVATAR_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Avatar image exceeds the 5MB size limit.",
        )

    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Avatar must be an image file.",
        )

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_secret_key = os.getenv("SUPABASE_SECRET_KEY")
    if not supabase_url or not supabase_secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Avatar upload failed.",
        )

    storage_path = f"{current_user.id}/{file.filename}"
    upload_url = (
        f"{supabase_url.rstrip('/')}/storage/v1/object/"
        f"{SUPABASE_AVATARS_BUCKET}/{storage_path}"
    )
    try:
        upload_response = httpx.post(
            upload_url,
            headers={
                "apikey": supabase_secret_key,
                "Authorization": f"Bearer {supabase_secret_key}",
                "Content-Type": file.content_type or "application/octet-stream",
                "x-upsert": "true",
            },
            content=file_bytes,
            timeout=30,
        )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Avatar upload failed.",
        )
    if upload_response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Avatar upload failed.",
        )

    avatar_url = (
        f"{supabase_url.rstrip('/')}/storage/v1/object/public/"
        f"{SUPABASE_AVATARS_BUCKET}/{current_user.id}/{file.filename}"
    )

    user_repository = UserRepository()
    try:
        updated_user = await user_repository.update_avatar(
            database_session=database_session,
            user_id=current_user.id,
            avatar_url=avatar_url,
        )
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception(
            "Failed to update avatar for user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Avatar could not be saved. Please try again or contact "
                "support if the problem persists."
            ),
        )

    return UserProfileResponse.model_validate(updated_user)
