from pydantic import BaseModel, Field
from typing import Optional


class DocumentData(BaseModel):
    full_name: Optional[str] = None
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    nationality: Optional[str] = None
    issuing_country: Optional[str] = None
    error: Optional[str] = None
    _warnings: Optional[list[str]] = None

    def to_dict(self) -> dict:
        return self.model_dump(exclude_none=False)

    @classmethod
    def from_dict(cls, data: dict) -> "DocumentData":
        return cls(**{k: v for k, v in data.items() if k in cls.model_fields})


class ComplianceResult(BaseModel):
    status: str = Field(description="PASS or FAIL")
    confidence_score: int = Field(description="Score 0-100", ge=0, le=100)
    reasons: list[str] = Field(description="Why it passed or failed")
    missing_documents: list[str] = Field(description="Missing or expired documents")
    recommendation: str = Field(description="What HR should do next")

    def to_dict(self) -> dict:
        return self.model_dump()


class HireProfile(BaseModel):
    full_name: str = "Unknown"
    family_size: int = 1
    monthly_budget_usd: float = 0.0
    destination_city: str = ""

    def to_dict(self) -> dict:
        return self.model_dump()
