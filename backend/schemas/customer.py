from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class CustomerCreate(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    risk_level: str = "low"
    pep_status: bool = False
    occupation: Optional[str] = None
    annual_income: Optional[float] = None
    source_of_funds: Optional[str] = None


class CustomerUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    risk_level: Optional[str] = None
    pep_status: Optional[bool] = None
    sanctions_flag: Optional[bool] = None
    occupation: Optional[str] = None
    source_of_funds: Optional[str] = None


class CustomerOut(BaseModel):
    id: int
    customer_number: str
    full_name: str
    email: Optional[str]
    phone: Optional[str]
    date_of_birth: Optional[date]
    nationality: Optional[str]
    id_type: Optional[str]
    id_number: Optional[str]
    address: Optional[str]
    country: Optional[str]
    risk_level: str
    pep_status: bool
    sanctions_flag: bool
    occupation: Optional[str]
    annual_income: Optional[float]
    source_of_funds: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class AccountCreate(BaseModel):
    customer_id: int
    account_type: str = "checking"
    currency: str = "USD"
    balance: float = 0.0
    country: Optional[str] = None
    iban: Optional[str] = None


class AccountOut(BaseModel):
    id: int
    account_number: str
    customer_id: int
    account_type: str
    currency: str
    balance: float
    status: str
    opened_date: Optional[date]
    country: Optional[str]

    class Config:
        from_attributes = True
