from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserProfileResponse(BaseModel):
    """Represent one product-level user profile."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: str
    display_name: str
    username: str
    avatar_url: str | None
    institution: str | None
    specialisation: str | None
    experience_years: int | None
    location: str | None
    medical_licence_number: str | None
    licence_document_url: str | None
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class ClinicianProfileUpdate(BaseModel):
    """Partial update schema for clinician profile polish."""

    institution: str | None = Field(default=None, max_length=100)
    specialisation: str | None = Field(default=None, max_length=50)
    experience_years: int | None = Field(default=None, ge=0, le=50)
    location: str | None = Field(default=None, max_length=100)


class ProfileUpdate(BaseModel):
    """Unified profile update schema for members and clinicians."""

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    username: str | None = Field(default=None, min_length=3, max_length=50, pattern=r"^[a-z0-9_]+$")
    institution: str | None = Field(default=None, max_length=100)
    specialisation: str | None = Field(default=None, max_length=50)
    experience_years: int | None = Field(default=None, ge=0, le=50)
    location: str | None = Field(default=None, max_length=100)


class PublicUserProfileResponse(BaseModel):
    """Represent one public user profile for community surfaces."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    username: str
    avatar_url: str | None
    role: str
    is_verified: bool
    institution: str | None
    specialisation: str | None
    experience_years: int | None
    location: str | None
    email: str | None
    followers_count: int
    following_count: int
    is_following: bool
