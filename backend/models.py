from typing import Optional
from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    id: str
    filename: str
    status: str = "PENDING"
    document_type: Optional[str] = None
    confidence_score: Optional[int] = None
    confidence_label: Optional[str] = None
    extracted_data: Optional[dict] = None
    date_errors: list[str] = []
    date_warnings: list[str] = []
    error: Optional[str] = None


class StageTransitionEntry(BaseModel):
    stage: str
    entered_at: str
    actor: str = "system"
    decision: Optional[str] = None
    details: Optional[str] = None


class CaseCreateRequest(BaseModel):
    full_name: str = Field(default="Unknown", max_length=200)
    family_size: int = Field(default=1, ge=1, le=20)
    monthly_budget_usd: float = Field(default=0.0, ge=0)


class CaseResponse(BaseModel):
    id: str
    status: str
    created_at: str
    updated_at: str
    destination_country: Optional[str] = None
    destination_city: Optional[str] = None
    hire_profile: Optional[dict] = None
    documents: list[dict] = []
    stages: list[dict] = []
    current_stage: Optional[str] = None
    compliance_result: Optional[dict] = None
    relocation_guide: Optional[str] = None
    error: Optional[str] = None


class CaseListResponse(BaseModel):
    id: str
    status: str
    created_at: str
    updated_at: str
    destination_country: Optional[str] = None
    destination_city: Optional[str] = None


class MaestroWebhookRequest(BaseModel):
    case_id: str
    action: str
    payload: dict = {}


class HrDecisionRequest(BaseModel):
    case_id: str
    decision: str
    reviewer_name: str = "HR Manager"
    comments: Optional[str] = None
