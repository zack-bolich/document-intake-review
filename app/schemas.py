from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import DocumentStatus


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    document_type: str
    document_number: str | None
    vendor: str | None
    amount: Decimal | None
    currency: str | None
    document_date: date | None
    confidence: Decimal
    field_confidence: dict[str, float]
    status: DocumentStatus
    duplicate_of_id: str | None
    retry_count: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None


class DocumentCorrection(BaseModel):
    document_type: str | None = None
    document_number: str | None = None
    vendor: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = None
    document_date: date | None = None
    actor: str = "reviewer"

    @field_validator("currency")
    @classmethod
    def valid_currency(cls, value: str | None):
        if value is not None and (len(value) != 3 or not value.isalpha()):
            raise ValueError("currency must be a three-letter code")
        return value.upper() if value else value


class ApprovalRequest(BaseModel):
    actor: str = "reviewer"


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    action: str
    actor: str
    details: dict
    created_at: datetime


class DeadLetterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    error: str
    raw_text_excerpt: str
    retry_count: int
    created_at: datetime
    updated_at: datetime

