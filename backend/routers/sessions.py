from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from core.dependencies import get_current_user, require_admin
from models.user import User
from models.session import UserSession
from datetime import datetime, timezone

router = APIRouter(prefix="/sessions", tags=["Sessions"])

@router.get("")
def list_sessions(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    sessions = db.query(UserSession).filter(UserSession.is_active == True).all()
    result = []
    for s in sessions:
        result.append({
            "id": s.id,
            "user_id": s.user_id,
            "username": s.user.username if s.user else "unknown",
            "full_name": s.user.full_name if s.user else "unknown",
            "role": s.user.role if s.user else "unknown",
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "last_seen": s.last_seen.isoformat() if s.last_seen else None,
        })
    return result

@router.delete("/{session_id}")
def force_logout(session_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.is_active = False
    db.commit()
    return {"message": "Session terminated"}

@router.delete("/user/{user_id}")
def force_logout_user(user_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    db.query(UserSession).filter(UserSession.user_id == user_id, UserSession.is_active == True).update({"is_active": False})
    db.commit()
    return {"message": f"All sessions for user {user_id} terminated"}
