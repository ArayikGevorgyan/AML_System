from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from core.dependencies import get_current_user
from models.user import User
from schemas.case import CaseCreate, CaseUpdate, CaseOut, CaseNoteCreate, CaseNoteOut
from services.case_service import case_service
from services.ai_summary_service import generate_case_summary

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post("", response_model=CaseOut)
def create_case(
    data: CaseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return case_service.create_case(data, db, current_user)


@router.get("")
def list_cases(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return case_service.list_cases(db, status, priority, assigned_to, page, page_size)


@router.get("/{case_id}", response_model=CaseOut)
def get_case(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return case_service.get_case(case_id, db)


@router.put("/{case_id}", response_model=CaseOut)
def update_case(
    case_id: int,
    data: CaseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return case_service.update_case(case_id, data, db, current_user)


@router.post("/{case_id}/notes", response_model=CaseNoteOut)
def add_note(
    case_id: int,
    data: CaseNoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return case_service.add_note(case_id, data, db, current_user)


@router.get("/{case_id}/notes", response_model=list[CaseNoteOut])
def get_notes(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return case_service.get_notes(case_id, db)


@router.get("/{case_id}/ai-summary")
def get_ai_summary(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate an AI-powered plain-English summary for a case."""
    return generate_case_summary(case_id, db)
