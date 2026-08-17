from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from api.schemas.assessment import ClinicalData


class MemberTopFactor(BaseModel):
    """Represent one plain-language risk factor for member display."""

    feature: str
    explanation: str


class MemberOodWarning(BaseModel):
    """Represent an out-of-distribution warning in plain language."""

    has_warning: bool
    flagged_features: list[str]
    severity: Literal["Minor", "Major", None] = None


class MemberManualAssessRequest(BaseModel):
    """
    Member self-assessment form — clinical data only with optional patient linkage.
    When patient_id is provided the assessment links to that existing patient;
    when omitted a new patient profile is created automatically.
    """

    first_name: str
    last_name: str
    patient_id: Optional[str] = None
    clinical_data: ClinicalData


class MemberAssessmentResponse(BaseModel):
    """Represent a member-facing assessment result with plain-language output only."""

    model_config = ConfigDict(from_attributes=True)

    assessment_id: UUID
    patient_id: str
    risk_level: str
    top_factors: list[MemberTopFactor]
    suggested_action: str
    model_limitations: str
    ood_warning: Optional[MemberOodWarning] = None
    created_at: datetime


class MemberAssessmentDetailResponse(BaseModel):
    """Represent a member assessment detail record for the report view."""

    assessment_id: UUID
    patient_id: str
    patient_name: str
    sample_date: str
    risk_level: str
    top_factors: list[MemberTopFactor]
    suggested_action: str
    model_limitations: str
    ood_warning: Optional[MemberOodWarning] = None
    created_at: datetime


class MemberAssessmentListItem(BaseModel):
    """Represent one item in a member assessment history listing."""

    id: UUID
    patient_name: str
    patient_id: str
    risk_level: str
    status: Literal["Success", "High risk"]
    created_at: datetime


class MemberAssessmentListResponse(BaseModel):
    """Represent a paginated member assessment history page."""

    total: int
    page: int
    page_size: int
    results: list[MemberAssessmentListItem]


class BannerItem(BaseModel):
    """Represent one awareness banner for the member home screen."""

    id: str
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    bg_color: str
    link_url: Optional[str] = None


class ResourceItem(BaseModel):
    """Represent one educational resource for the member explore tab."""

    id: str
    title: str
    category: Literal["Awareness", "Self-Exam", "FAQ", "Treatment"]
    summary: str
    content_url: Optional[str] = None
    type: Literal["article", "video", "faq"]
