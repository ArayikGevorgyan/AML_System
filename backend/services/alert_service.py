import json
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from models.alert import Alert
from models.transaction import Transaction
from models.user import User
from services.rules_engine import RuleMatch
from services.audit_service import audit_service


def _generate_alert_number(db: Session) -> str:
    count = db.query(Alert).count()
    today = datetime.now().strftime("%Y%m%d")
    return f"ALT-{today}-{count + 1:05d}"


class AlertService:

    def create_alerts_from_matches(
        self,
        matches: List[RuleMatch],
        transaction: Transaction,
        db: Session,
    ) -> List[Alert]:
        created = []
        for match in matches:
            alert = Alert(
                alert_number=_generate_alert_number(db),
                transaction_id=transaction.id,
                customer_id=transaction.from_customer_id,
                rule_id=match.rule_id,
                severity=match.severity,
                status="open",
                reason=match.reason,
                details=json.dumps(match.details),
                risk_score=match.risk_score,
            )
            db.add(alert)
            db.flush()
            created.append(alert)

        if created:
            transaction.flagged = True
            transaction.risk_score = max(m.risk_score for m in matches)
            db.commit()
            for a in created:
                db.refresh(a)
        return created

    def get_alert(self, alert_id: int, db: Session) -> Alert:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        return alert

    def list_alerts(
        self,
        db: Session,
        customer_id: Optional[int] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ):
        query = db.query(Alert)
        if customer_id:
            query = query.filter(Alert.customer_id == customer_id)
        if severity:
            query = query.filter(Alert.severity == severity)
        if status:
            query = query.filter(Alert.status == status)
        total = query.count()
        items = (
            query.order_by(Alert.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    def update_alert(
        self, alert_id: int, data: dict, db: Session, user: User
    ) -> Alert:
        alert = self.get_alert(alert_id, db)
        old = {"status": alert.status, "assigned_to": alert.assigned_to}

        for key, val in data.items():
            if val is not None and hasattr(alert, key):
                setattr(alert, key, val)

        if data.get("status") in ("closed", "false_positive"):
            alert.closed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(alert)
        audit_service.log(
            db, action="UPDATE_ALERT", user=user,
            entity_type="alert", entity_id=alert_id,
            old_value=old,
            new_value={"status": alert.status, "assigned_to": alert.assigned_to},
        )
        return alert

    def get_alerts_stats(self, db: Session) -> dict:
        from sqlalchemy import func
        stats = {}
        for sev in ("low", "medium", "high", "critical"):
            stats[sev] = db.query(func.count(Alert.id)).filter(
                Alert.severity == sev, Alert.status == "open"
            ).scalar() or 0
        return stats


alert_service = AlertService()
