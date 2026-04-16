from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from core.dependencies import get_current_user, require_roles
from services.escalation_service import run_all_escalation_rules, get_escalation_candidates

router = APIRouter(prefix="/escalation", tags=["Alert Escalation"])


@router.get("/candidates")
def escalation_candidates(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Preview alerts that would be escalated without running escalation."""
    return get_escalation_candidates(db)


@router.post("/run")
def run_escalation(
    db: Session = Depends(get_db),
    _=Depends(require_roles(["admin", "supervisor"])),
):
    """Run all escalation rules and return a summary of actions taken."""
    return run_all_escalation_rules(db)
