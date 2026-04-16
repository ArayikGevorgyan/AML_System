from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from core.dependencies import get_current_user, require_roles
from services.reporting_service import (
    monthly_transaction_summary,
    alert_statistics_report,
    sar_summary_report,
    customer_risk_distribution_report,
    rule_performance_report,
    full_compliance_export,
)

router = APIRouter(prefix="/reports", tags=["Reporting"])


@router.get("/transactions/monthly")
def transaction_monthly_report(
    year:  int = Query(default=datetime.now().year),
    month: int = Query(default=datetime.now().month),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Monthly transaction summary report."""
    return monthly_transaction_summary(db, year, month)


@router.get("/alerts")
def alert_stats_report(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Alert statistics for the last N days."""
    return alert_statistics_report(db, days)


@router.get("/sar")
def sar_report(
    year: int = Query(default=datetime.now().year),
    db: Session = Depends(get_db),
    _=Depends(require_roles(["admin", "supervisor"])),
):
    """SAR filing summary for a given year."""
    return sar_summary_report(db, year)


@router.get("/customers/risk-distribution")
def risk_distribution_report(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Customer risk level distribution report."""
    return customer_risk_distribution_report(db)


@router.get("/rules/performance")
def rules_performance_report(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """AML rule performance metrics."""
    return rule_performance_report(db, days)


@router.get("/export/full")
def full_export(
    db: Session = Depends(get_db),
    _=Depends(require_roles(["admin", "supervisor"])),
):
    """Full compliance export — all reports combined."""
    return full_compliance_export(db)
