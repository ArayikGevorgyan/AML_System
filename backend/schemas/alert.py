from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AlertOut(BaseModel):
    id: int
    alert_number: str
    transaction_id: Optional[int]
    customer_id: int
    rule_id: Optional[int]
    severity: str
    status: str
    reason: str
    details: Optional[str]
    risk_score: float
    assigned_to: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]
    closed_at: Optional[datetime]

    class Config:
        from_attributes = True


class AlertUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[int] = None
    severity: Optional[str] = None


class AlertFilter(BaseModel):
    customer_id: Optional[int] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    rule_id: Optional[int] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    assigned_to: Optional[int] = None
    page: int = 1
    page_size: int = 50


class RuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: str
    threshold_amount: Optional[float] = None
    threshold_count: Optional[int] = None
    time_window_hours: Optional[int] = None
    high_risk_countries: Optional[str] = None
    severity: str = "medium"


class RuleOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    category: str
    threshold_amount: Optional[float]
    threshold_count: Optional[int]
    time_window_hours: Optional[int]
    high_risk_countries: Optional[str]
    severity: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
