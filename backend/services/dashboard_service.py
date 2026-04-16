from datetime import datetime, timedelta, timezone, date
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.transaction import Transaction
from models.alert import Alert
from models.case import Case
from models.customer import Customer
from models.audit_log import AuditLog
from models.rule import Rule
from schemas.dashboard import (
    KPIStats, AlertsBySeverity, TransactionTimeSeries,
    AlertsTimeSeries, TopRuleTriggered, RecentAlert, DashboardResponse
)


class DashboardService:

    def get_dashboard(self, db: Session) -> DashboardResponse:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        txn_today_count = db.query(func.count(Transaction.id)).filter(
            Transaction.created_at >= today_start
        ).scalar() or 0

        txn_month_count = db.query(func.count(Transaction.id)).filter(
            Transaction.created_at >= month_start
        ).scalar() or 0

        txn_today_vol = db.query(func.sum(Transaction.amount)).filter(
            Transaction.created_at >= today_start
        ).scalar() or 0.0

        txn_month_vol = db.query(func.sum(Transaction.amount)).filter(
            Transaction.created_at >= month_start
        ).scalar() or 0.0

        open_alerts = db.query(func.count(Alert.id)).filter(
            Alert.status == "open"
        ).scalar() or 0

        high_critical = db.query(func.count(Alert.id)).filter(
            Alert.status == "open",
            Alert.severity.in_(["high", "critical"])
        ).scalar() or 0

        open_cases = db.query(func.count(Case.id)).filter(
            Case.status.in_(["open", "investigating", "pending_review"])
        ).scalar() or 0

        high_risk_customers = db.query(func.count(Customer.id)).filter(
            Customer.risk_level.in_(["high", "critical"])
        ).scalar() or 0

        sanctions_checks = db.query(func.count(AuditLog.id)).filter(
            AuditLog.action == "SANCTIONS_SEARCH",
            AuditLog.created_at >= today_start,
        ).scalar() or 0

        flagged_today = db.query(func.count(Transaction.id)).filter(
            Transaction.flagged == True,
            Transaction.created_at >= today_start,
        ).scalar() or 0

        kpis = KPIStats(
            total_transactions_today=txn_today_count,
            total_transactions_month=txn_month_count,
            total_volume_today=round(txn_today_vol, 2),
            total_volume_month=round(txn_month_vol, 2),
            open_alerts=open_alerts,
            high_critical_alerts=high_critical,
            open_cases=open_cases,
            high_risk_customers=high_risk_customers,
            sanctions_checks_today=sanctions_checks,
            flagged_transactions_today=flagged_today,
        )

        alerts_by_sev = AlertsBySeverity(
            low=db.query(func.count(Alert.id)).filter(Alert.severity == "low", Alert.status == "open").scalar() or 0,
            medium=db.query(func.count(Alert.id)).filter(Alert.severity == "medium", Alert.status == "open").scalar() or 0,
            high=db.query(func.count(Alert.id)).filter(Alert.severity == "high", Alert.status == "open").scalar() or 0,
            critical=db.query(func.count(Alert.id)).filter(Alert.severity == "critical", Alert.status == "open").scalar() or 0,
        )

        dates, amounts, counts = [], [], []
        for i in range(29, -1, -1):
            day = (now - timedelta(days=i)).date()
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())
            vol = db.query(func.sum(Transaction.amount)).filter(
                Transaction.created_at.between(day_start, day_end)
            ).scalar() or 0.0
            cnt = db.query(func.count(Transaction.id)).filter(
                Transaction.created_at.between(day_start, day_end)
            ).scalar() or 0
            dates.append(day.strftime("%Y-%m-%d"))
            amounts.append(round(vol, 2))
            counts.append(cnt)

        txn_series = TransactionTimeSeries(dates=dates, amounts=amounts, counts=counts)

        alert_dates, alert_counts = [], []
        for i in range(29, -1, -1):
            day = (now - timedelta(days=i)).date()
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())
            cnt = db.query(func.count(Alert.id)).filter(
                Alert.created_at.between(day_start, day_end)
            ).scalar() or 0
            alert_dates.append(day.strftime("%Y-%m-%d"))
            alert_counts.append(cnt)

        alerts_series = AlertsTimeSeries(dates=alert_dates, counts=alert_counts)

        from models.rule import Rule
        top_rule_rows = (
            db.query(Alert.rule_id, func.count(Alert.id).label("cnt"))
            .filter(Alert.rule_id.isnot(None))
            .group_by(Alert.rule_id)
            .order_by(func.count(Alert.id).desc())
            .limit(5)
            .all()
        )
        top_rules = []
        for rule_id, cnt in top_rule_rows:
            rule = db.query(Rule).filter(Rule.id == rule_id).first()
            if rule:
                top_rules.append(TopRuleTriggered(
                    rule_name=rule.name, count=cnt, severity=rule.severity
                ))

        recent_alert_rows = (
            db.query(Alert, Customer)
            .join(Customer, Alert.customer_id == Customer.id)
            .filter(Alert.status == "open")
            .order_by(Alert.created_at.desc())
            .limit(10)
            .all()
        )
        recent_alerts = [
            RecentAlert(
                id=a.id,
                alert_number=a.alert_number,
                customer_name=c.full_name,
                severity=a.severity,
                status=a.status,
                reason=a.reason[:80] + "..." if len(a.reason) > 80 else a.reason,
                created_at=a.created_at.strftime("%Y-%m-%d %H:%M"),
            )
            for a, c in recent_alert_rows
        ]

        cases_by_status = {}
        for st in ("open", "investigating", "pending_review", "escalated", "closed", "filed_sar"):
            cases_by_status[st] = db.query(func.count(Case.id)).filter(Case.status == st).scalar() or 0

        return DashboardResponse(
            kpis=kpis,
            alerts_by_severity=alerts_by_sev,
            transaction_series=txn_series,
            alerts_series=alerts_series,
            top_rules=top_rules,
            recent_alerts=recent_alerts,
            cases_by_status=cases_by_status,
        )


dashboard_service = DashboardService()
