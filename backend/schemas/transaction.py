from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TransactionCreate(BaseModel):
    from_account_id: Optional[int] = None
    to_account_id: Optional[int] = None
    from_customer_id: Optional[int] = None
    to_customer_id: Optional[int] = None
    amount: float
    currency: str = "USD"
    transaction_type: str
    description: Optional[str] = None
    originating_country: Optional[str] = None
    destination_country: Optional[str] = None
    channel: Optional[str] = "online"


class TransactionOut(BaseModel):
    id: int
    reference: str
    from_account_id: Optional[int]
    to_account_id: Optional[int]
    from_customer_id: Optional[int]
    to_customer_id: Optional[int]
    amount: float
    currency: str
    transaction_type: str
    status: str
    description: Optional[str]
    originating_country: Optional[str]
    destination_country: Optional[str]
    is_international: bool
    channel: Optional[str]
    risk_score: float
    flagged: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionFilter(BaseModel):
    customer_id: Optional[int] = None
    transaction_type: Optional[str] = None
    status: Optional[str] = None
    flagged: Optional[bool] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    originating_country: Optional[str] = None
    page: int = 1
    page_size: int = 50
