from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from core.dependencies import get_current_user
from models.user import User
from schemas.alert import AlertOut, AlertUpdate
from services.alert_service import alert_service

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("")
def list_alerts(
    customer_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return alert_service.list_alerts(db, customer_id, severity, status, page, page_size)


@router.get("/stats")
def alert_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return alert_service.get_alerts_stats(db)


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return alert_service.get_alert(alert_id, db)


@router.put("/mark-all-read")
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from models.alert import Alert
    updated = db.query(Alert).filter(Alert.status == "open").update({"status": "under_review"})
    db.commit()
    return {"updated": updated}


@router.put("/{alert_id}", response_model=AlertOut)
def update_alert(
    alert_id: int,
    data: AlertUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return alert_service.update_alert(
        alert_id, data.model_dump(exclude_none=True), db, current_user
    )
