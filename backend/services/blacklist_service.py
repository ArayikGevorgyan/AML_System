from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from models.blacklist import BlacklistEntry, BlacklistMovementLog


VALID_TYPES     = {"ip", "country", "entity", "email", "account"}
VALID_LIST_TYPES = {"black", "yellow", "white"}


def add_entry(
    db: Session,
    entry_type: str,
    value: str,
    reason: str,
    severity: str = "high",
    list_type: str = "black",
    added_by: Optional[int] = None,
    expires_at: Optional[datetime] = None,
) -> BlacklistEntry:
    if entry_type not in VALID_TYPES:
        raise ValueError(f"Invalid entry_type. Must be one of: {VALID_TYPES}")
    if list_type not in VALID_LIST_TYPES:
        raise ValueError(f"Invalid list_type. Must be one of: {VALID_LIST_TYPES}")

    existing = db.query(BlacklistEntry).filter(
        BlacklistEntry.entry_type == entry_type,
        BlacklistEntry.value == value.strip().lower(),
        BlacklistEntry.is_active == True,
    ).first()
    if existing:
        raise ValueError(f"Active entry already exists for {entry_type}: {value}")

    entry = BlacklistEntry(
        entry_type=entry_type,
        value=value.strip().lower(),
        reason=reason,
        severity=severity,
        list_type=list_type,
        added_by=added_by,
        expires_at=expires_at,
        is_active=True,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    log = BlacklistMovementLog(
        entry_id=entry.id,
        from_list="none",
        to_list=list_type,
        reason=f"Initial entry: {reason}",
        moved_by=added_by,
    )
    db.add(log)
    db.commit()

    return entry


def move_entry(
    db: Session,
    entry_id: int,
    to_list: str,
    reason: str,
    moved_by_user=None,
    review_note: Optional[str] = None,
) -> BlacklistEntry:
    if to_list not in VALID_LIST_TYPES:
        raise ValueError(f"Invalid list_type. Must be one of: {VALID_LIST_TYPES}")

    entry = db.query(BlacklistEntry).filter(BlacklistEntry.id == entry_id).first()
    if not entry:
        raise ValueError("Entry not found")

    from_list = entry.list_type
    entry.list_type = to_list
    if review_note:
        entry.review_note = review_note

    log = BlacklistMovementLog(
        entry_id=entry.id,
        from_list=from_list,
        to_list=to_list,
        reason=reason,
        moved_by=moved_by_user.id if moved_by_user else None,
        moved_by_name=moved_by_user.full_name if moved_by_user else None,
    )
    db.add(log)
    db.commit()
    db.refresh(entry)
    return entry


def get_movement_history(db: Session, entry_id: int) -> list:
    return db.query(BlacklistMovementLog).filter(
        BlacklistMovementLog.entry_id == entry_id
    ).order_by(BlacklistMovementLog.created_at.desc()).all()


def remove_entry(db: Session, entry_id: int) -> bool:
    entry = db.query(BlacklistEntry).filter(BlacklistEntry.id == entry_id).first()
    if not entry:
        return False
    entry.is_active = False
    db.commit()
    return True


def get_all_entries(
    db: Session,
    entry_type: Optional[str] = None,
    list_type: Optional[str] = None,
    active_only: bool = True,
) -> list:
    query = db.query(BlacklistEntry)
    if active_only:
        query = query.filter(BlacklistEntry.is_active == True)
    if entry_type:
        query = query.filter(BlacklistEntry.entry_type == entry_type)
    if list_type:
        query = query.filter(BlacklistEntry.list_type == list_type)
    return query.order_by(BlacklistEntry.created_at.desc()).all()


def is_blacklisted(db: Session, entry_type: str, value: str) -> Optional[BlacklistEntry]:
    now = datetime.now(timezone.utc)
    entry = db.query(BlacklistEntry).filter(
        BlacklistEntry.entry_type == entry_type,
        BlacklistEntry.value == value.strip().lower(),
        BlacklistEntry.is_active == True,
    ).first()

    if not entry:
        return None

    if entry.expires_at and entry.expires_at < now:
        entry.is_active = False
        db.commit()
        return None

    return entry


def get_list_status(db: Session, entry_type: str, value: str) -> Optional[dict]:
    entry = is_blacklisted(db, entry_type, value)
    if not entry:
        return None
    return {
        "list_type": entry.list_type,
        "reason": entry.reason,
        "severity": entry.severity,
        "review_note": entry.review_note,
        "entry_id": entry.id,
    }


def screen_transaction(db: Session, transaction) -> list:
    hits = []
    for country in [transaction.originating_country, transaction.destination_country]:
        if country:
            hit = is_blacklisted(db, "country", country.lower())
            if hit:
                hits.append(hit)
    return hits


def get_blacklist_stats(db: Session) -> dict:
    total = db.query(BlacklistEntry).filter(BlacklistEntry.is_active == True).count()
    by_type = {}
    for t in VALID_TYPES:
        by_type[t] = db.query(BlacklistEntry).filter(
            BlacklistEntry.entry_type == t,
            BlacklistEntry.is_active == True,
        ).count()

    by_list = {}
    for lt in VALID_LIST_TYPES:
        by_list[lt] = db.query(BlacklistEntry).filter(
            BlacklistEntry.list_type == lt,
            BlacklistEntry.is_active == True,
        ).count()

    return {
        "total_active": total,
        "by_type": by_type,
        "by_list": by_list,
    }
