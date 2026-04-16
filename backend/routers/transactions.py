from typing import Optional
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import Integer

from database import get_db
from core.dependencies import get_current_user
from models.user import User
from models.transaction import Transaction
from schemas.transaction import TransactionCreate, TransactionOut, TransactionFilter
from services.transaction_service import transaction_service

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("", response_model=TransactionOut)
def create_transaction(
    data: TransactionCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return transaction_service.create_transaction(data, db, current_user, background_tasks)


@router.get("")
def list_transactions(
    customer_id: Optional[int] = Query(None),
    transaction_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    flagged: Optional[bool] = Query(None),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    originating_country: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = TransactionFilter(
        customer_id=customer_id,
        transaction_type=transaction_type,
        status=status,
        flagged=flagged,
        min_amount=min_amount,
        max_amount=max_amount,
        originating_country=originating_country,
        page=page,
        page_size=page_size,
    )
    return transaction_service.list_transactions(filters, db)



@router.get("/by-country")
def transactions_by_country(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns transaction counts and volumes grouped by originating country."""
    from sqlalchemy import func
    results = db.query(
        Transaction.originating_country,
        func.count(Transaction.id).label("count"),
        func.sum(Transaction.amount).label("volume"),
        func.sum(func.cast(Transaction.flagged, Integer)).label("flagged_count"),
    ).filter(Transaction.originating_country != None).group_by(Transaction.originating_country).all()

    return [{"country": r[0], "count": r[1], "volume": round(r[2] or 0, 2), "flagged_count": r[3] or 0} for r in results]


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return transaction_service.get_transaction(transaction_id, db)
