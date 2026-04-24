import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ResultSummary(BaseModel):
    label: str
    confidence: Optional[float]
    classifier_version: str
    classified_at: datetime

    model_config = {"from_attributes": True}


class SubmissionAdminResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    age: int
    place_of_living: str
    gender: str
    country_of_origin: str
    description: Optional[str]
    photo_url: Optional[str] = None
    status: str
    result: Optional[ResultSummary] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SubmissionListAdminResponse(BaseModel):
    data: list[SubmissionAdminResponse]
    total: int
    page: int
    per_page: int


class UserAdminResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListAdminResponse(BaseModel):
    data: list[UserAdminResponse]
    total: int
    page: int
    per_page: int
