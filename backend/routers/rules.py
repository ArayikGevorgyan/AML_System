from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from core.dependencies import get_current_user, require_supervisor_or_admin
from models.user import User
from models.rule import Rule
from schemas.alert import RuleCreate, RuleOut
from services.audit_service import audit_service

router = APIRouter(prefix="/rules", tags=["AML Rules"])


@router.get("", response_model=list[RuleOut])
def list_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(Rule).order_by(Rule.created_at.desc()).all()


@router.post("", response_model=RuleOut)
def create_rule(
    data: RuleCreate,
    current_user: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db),
):
    rule = Rule(
        name=data.name,
        description=data.description,
        category=data.category,
        threshold_amount=data.threshold_amount,
        threshold_count=data.threshold_count,
        time_window_hours=data.time_window_hours,
        high_risk_countries=data.high_risk_countries,
        severity=data.severity,
        created_by=current_user.id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    audit_service.log(
        db, action="CREATE_RULE", user=current_user,
        entity_type="rule", entity_id=rule.id,
        new_value={"name": rule.name, "category": rule.category},
    )
    return rule


@router.put("/{rule_id}", response_model=RuleOut)
def update_rule(
    rule_id: int,
    data: RuleCreate,
    current_user: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for key, val in data.model_dump(exclude_none=True).items():
        setattr(rule, key, val)
    db.commit()
    db.refresh(rule)
    audit_service.log(db, action="UPDATE_RULE", user=current_user, entity_type="rule", entity_id=rule_id)
    return rule


@router.patch("/{rule_id}/toggle")
def toggle_rule(
    rule_id: int,
    current_user: User = Depends(require_supervisor_or_admin),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_active = not rule.is_active
    db.commit()
    return {"id": rule.id, "is_active": rule.is_active}
