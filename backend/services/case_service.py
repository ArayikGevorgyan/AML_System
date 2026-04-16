from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from models.case import Case, CaseNote
from models.alert import Alert
from models.user import User
from schemas.case import CaseCreate, CaseUpdate, CaseNoteCreate
from services.audit_service import audit_service


def _generate_case_number(db: Session) -> str:
    count = db.query(Case).count()
    year = datetime.now().year
    return f"CASE-{year}-{count + 1:05d}"


class CaseService:

    def create_case(self, data: CaseCreate, db: Session, user: User) -> Case:
        if data.alert_id:
            alert = db.query(Alert).filter(Alert.id == data.alert_id).first()
            if not alert:
                raise HTTPException(status_code=404, detail="Alert not found")
            alert.status = "under_review"

        case = Case(
            case_number=_generate_case_number(db),
            alert_id=data.alert_id,
            title=data.title,
            description=data.description,
            priority=data.priority,
            assigned_to=data.assigned_to,
            created_by=user.id,
        )
        db.add(case)
        db.commit()
        db.refresh(case)

        note = CaseNote(
            case_id=case.id,
            user_id=user.id,
            note=f"Case created from alert #{data.alert_id}" if data.alert_id else "Case created manually.",
            note_type="status_change",
        )
        db.add(note)
        db.commit()

        audit_service.log(
            db, action="CREATE_CASE", user=user,
            entity_type="case", entity_id=case.id,
            new_value={"case_number": case.case_number, "priority": case.priority},
        )
        return case

    def get_case(self, case_id: int, db: Session) -> Case:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        return case

    def list_cases(
        self,
        db: Session,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_to: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ):
        query = db.query(Case)
        if status:
            query = query.filter(Case.status == status)
        if priority:
            query = query.filter(Case.priority == priority)
        if assigned_to:
            query = query.filter(Case.assigned_to == assigned_to)
        total = query.count()
        items = (
            query.order_by(Case.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    def update_case(self, case_id: int, data: CaseUpdate, db: Session, user: User) -> Case:
        case = self.get_case(case_id, db)
        old_status = case.status
        old_assigned = case.assigned_to

        if data.status in ("escalated", "filed_sar") and user.role == "analyst":
            raise HTTPException(
                status_code=403,
                detail=f"Analysts cannot set case status to '{data.status}'. Supervisor or Admin required.",
            )

        for key, val in data.model_dump(exclude_none=True).items():
            setattr(case, key, val)

        if data.status in ("closed", "filed_sar"):
            case.closed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(case)

        if data.status and data.status != old_status:
            note = CaseNote(
                case_id=case_id,
                user_id=user.id,
                note=f"Status changed from '{old_status}' to '{data.status}'",
                note_type="status_change",
            )
            db.add(note)
            db.commit()

        audit_service.log(
            db, action="UPDATE_CASE", user=user,
            entity_type="case", entity_id=case_id,
            old_value={"status": old_status},
            new_value={"status": case.status},
        )
        return case

    def add_note(self, case_id: int, data: CaseNoteCreate, db: Session, user: User) -> CaseNote:
        self.get_case(case_id, db)
        note = CaseNote(
            case_id=case_id,
            user_id=user.id,
            note=data.note,
            note_type=data.note_type,
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        audit_service.log(
            db, action="ADD_CASE_NOTE", user=user,
            entity_type="case", entity_id=case_id,
        )
        return note

    def get_notes(self, case_id: int, db: Session):
        return db.query(CaseNote).filter(CaseNote.case_id == case_id).order_by(CaseNote.created_at).all()


case_service = CaseService()
