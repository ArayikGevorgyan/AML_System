from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from core.dependencies import get_current_user
from models.user import User
from schemas.customer import CustomerCreate, CustomerUpdate, CustomerOut, AccountCreate, AccountOut
from services.customer_service import customer_service

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post("", response_model=CustomerOut)
def create_customer(
    data: CustomerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return customer_service.create_customer(data, db, current_user)


@router.get("")
def list_customers(
    risk_level: Optional[str] = Query(None),
    pep_status: Optional[bool] = Query(None),
    sanctions_flag: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return customer_service.list_customers(
        db, risk_level, pep_status, sanctions_flag, search, page, page_size
    )


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return customer_service.get_customer(customer_id, db)


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return customer_service.update_customer(customer_id, data, db, current_user)


@router.get("/{customer_id}/accounts", response_model=list[AccountOut])
def get_customer_accounts(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return customer_service.get_customer_accounts(customer_id, db)


@router.post("/accounts", response_model=AccountOut)
def create_account(
    data: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return customer_service.create_account(data, db, current_user)
