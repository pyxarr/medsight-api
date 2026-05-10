from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
