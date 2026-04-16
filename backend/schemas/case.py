from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CaseCreate(BaseModel):
    alert_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    assigned_to: Optional[int] = None


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[int] = None
    resolution: Optional[str] = None
    sar_filed: Optional[bool] = None
    sar_reference: Optional[str] = None


class CaseOut(BaseModel):
    id: int
    case_number: str
    alert_id: Optional[int]
    title: str
    description: Optional[str]
    status: str
    priority: str
    assigned_to: Optional[int]
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime]
    closed_at: Optional[datetime]
    resolution: Optional[str]
    sar_filed: bool
    sar_reference: Optional[str]

    class Config:
        from_attributes = True


class CaseNoteCreate(BaseModel):
    note: str
    note_type: str = "comment"


class CaseNoteOut(BaseModel):
    id: int
    case_id: int
    user_id: int
    note: str
    note_type: str
    created_at: datetime

    class Config:
        from_attributes = True
