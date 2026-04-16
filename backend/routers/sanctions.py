from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from core.dependencies import get_current_user, require_admin
from models.user import User
from models.sanctions import SanctionsEntry
from schemas.sanctions import SanctionsSearchRequest, SanctionsSearchResponse, SanctionsEntryOut
from services.sanctions_screener import sanctions_screener
from services.audit_service import audit_service

router = APIRouter(prefix="/sanctions", tags=["Sanctions Screening"])


@router.post("/search", response_model=SanctionsSearchResponse)
def search_sanctions(
    request: SanctionsSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = sanctions_screener.search(request, db)
    audit_service.log(
        db,
        action="SANCTIONS_SEARCH",
        user=current_user,
        description=f"Searched for '{request.name}' — {result.total_results} results",
    )
    return result


@router.get("/entries")
def list_entries(
    search: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    program: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(SanctionsEntry)
    if search:
        query = query.filter(SanctionsEntry.primary_name.ilike(f"%{search}%"))
    if entity_type:
        query = query.filter(SanctionsEntry.entity_type == entity_type)
    if program:
        query = query.filter(SanctionsEntry.programs.contains(program))
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/stats")
def sanctions_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from sqlalchemy import func
    from models.sanctions import SanctionsAlias

    total_entries = db.query(func.count(SanctionsEntry.id)).scalar() or 0
    total_aliases = db.query(func.count(SanctionsAlias.id)).scalar() or 0

    by_type = (
        db.query(SanctionsEntry.entity_type, func.count(SanctionsEntry.id))
        .group_by(SanctionsEntry.entity_type)
        .all()
    )
    by_list_raw = (
        db.query(SanctionsEntry.list_name, func.count(SanctionsEntry.id))
        .group_by(SanctionsEntry.list_name)
        .all()
    )

    # Normalise list names for consistent frontend display
    by_list: dict = {}
    ofac_count = 0
    un_count = 0
    for ln, cnt in by_list_raw:
        if not ln:
            continue
        by_list[ln] = cnt
        ln_lower = ln.lower()
        if "sdn" in ln_lower or "ofac" in ln_lower:
            ofac_count += cnt
        elif "un" in ln_lower or "consolidated" in ln_lower:
            un_count += cnt

    return {
        "total_entries":  total_entries,
        "total_aliases":  total_aliases,
        "ofac_entries":   ofac_count,
        "un_entries":     un_count,
        "programs_count": 86,
        "countries_count": 196,
        "by_entity_type": {t: c for t, c in by_type if t},
        "by_list":        by_list,
    }


@router.post("/import")
def import_sdn(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Re-import the SDN XML file. Admin only."""
    import subprocess, sys
    from pathlib import Path
    script = Path(__file__).parent.parent / "scripts" / "import_sanctions.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr)
    audit_service.log(db, action="IMPORT_SDN", user=current_user)
    return {"message": "SDN import completed", "output": result.stdout[-500:]}
