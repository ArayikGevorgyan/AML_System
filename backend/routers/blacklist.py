from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from core.dependencies import get_current_user, require_roles, require_admin
from services.blacklist_service import (
    add_entry, remove_entry, get_all_entries, move_entry,
    is_blacklisted, screen_transaction, get_blacklist_stats,
    get_movement_history,
)

router = APIRouter(prefix="/blacklist", tags=["Blacklist"])


class BlacklistCreate(BaseModel):
    entry_type: str
    value: str
    reason: str
    severity: str = "high"
    list_type: str = "black"
    expires_at: Optional[datetime] = None


class BlacklistCheck(BaseModel):
    entry_type: str
    value: str


class MoveEntry(BaseModel):
    to_list: str
    reason: str
    review_note: Optional[str] = None


@router.get("")
def list_entries(
    entry_type: Optional[str] = None,
    list_type: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    entries = get_all_entries(db, entry_type=entry_type, list_type=list_type, active_only=active_only)
    return [
        {
            "id":          e.id,
            "entry_type":  e.entry_type,
            "value":       e.value,
            "reason":      e.reason,
            "severity":    e.severity,
            "list_type":   e.list_type,
            "is_active":   e.is_active,
            "review_note": e.review_note,
            "created_at":  e.created_at,
            "expires_at":  e.expires_at,
        }
        for e in entries
    ]


@router.get("/stats")
def blacklist_stats(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return get_blacklist_stats(db)


@router.post("/check")
def check_entry(body: BlacklistCheck, db: Session = Depends(get_db), _=Depends(get_current_user)):
    hit = is_blacklisted(db, body.entry_type, body.value)
    return {
        "is_blacklisted": hit is not None,
        "entry": {
            "id":          hit.id,
            "reason":      hit.reason,
            "severity":    hit.severity,
            "list_type":   hit.list_type,
            "review_note": hit.review_note,
        } if hit else None,
    }


@router.post("", status_code=201)
def create_entry(
    body: BlacklistCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "supervisor")),
):
    try:
        entry = add_entry(
            db,
            entry_type=body.entry_type,
            value=body.value,
            reason=body.reason,
            severity=body.severity,
            list_type=body.list_type,
            added_by=current_user.id,
            expires_at=body.expires_at,
        )
        return {"id": entry.id, "message": f"Entry added to {body.list_type}list."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{entry_id}/move")
def move_to_list(
    entry_id: int,
    body: MoveEntry,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "supervisor")),
):
    try:
        entry = move_entry(
            db,
            entry_id=entry_id,
            to_list=body.to_list,
            reason=body.reason,
            moved_by_user=current_user,
            review_note=body.review_note,
        )
        return {"message": f"Entry moved to {body.to_list}list.", "list_type": entry.list_type}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{entry_id}/history")
def entry_history(
    entry_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    logs = get_movement_history(db, entry_id)
    return [
        {
            "from_list":    l.from_list,
            "to_list":      l.to_list,
            "reason":       l.reason,
            "moved_by":     l.moved_by_name,
            "created_at":   l.created_at,
        }
        for l in logs
    ]


@router.delete("/{entry_id}")
def delete_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    success = remove_entry(db, entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"message": "Blacklist entry deactivated."}
