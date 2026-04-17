"""
Compliance Report Generator
==============================
Generates monthly, quarterly, and annual compliance reports for AML operations.
Reports contain transaction statistics, alert metrics, case outcomes, rule
performance, and executive KPI summaries.

Usage:
    from reports.compliance_report import ComplianceReportGenerator
    from database import SessionLocal

    db = SessionLocal()
    gen = ComplianceReportGenerator()
    report = gen.monthly_report(db, year=2024, month=3)
    summary = gen.generate_executive_summary(db, days=30)
"""

from datetime import datetime, timedelta, timezone
from calendar import monthrange
from typing import List, Dict, Any, Optional


class ComplianceReportGenerator:
    """
    Generates structured compliance reports for AML operations.

    All methods return plain dict structures suitable for JSON serialisation,
    API responses, or further rendering into PDF/Excel.
    """

    def __init__(self) -> None:
        """Initialize the report generator."""
        self._now = lambda: datetime.now(timezone.utc)

    def _period_bounds(self, year: int, month: int) -> tuple:
        """Return (start_dt, end_dt) for a given year/month."""
        _, last_day = monthrange(year, month)
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
        return start, end

    # ---------------------------------------------------------------------------
    # monthly_report
    # ---------------------------------------------------------------------------

    def monthly_report(self, db: Any, year: int, month: int) -> Dict[str, Any]:
        """
        Generate a comprehensive monthly compliance report.

        Args:
            db:    SQLAlchemy session.
            year:  Report year (e.g. 2024).
            month: Report month (1–12).

        Returns:
            Dict with transaction stats, alert stats, case outcomes,
            rule performance, and KPI summary for the month.
        """
        from models.transaction import Transaction
        from models.alert import Alert
        from models.case import Case
        from models.customer import Customer
        from models.rule import Rule

        start, end = self._period_bounds(year, month)

        # --- Transactions ---
        txns = db.query(Transaction).filter(
            Transaction.created_at >= start,
            Transaction.created_at <= end,
        ).all()

        txn_total = len(txns)
        txn_volume = sum(t.amount or 0 for t in txns)
        txn_flagged = sum(1 for t in txns if t.flagged)
        txn_intl = sum(1 for t in txns if t.is_international)

        by_type: Dict[str, int] = {}
        by_currency: Dict[str, float] = {}
        for t in txns:
            tt = t.transaction_type or "unknown"
            by_type[tt] = by_type.get(tt, 0) + 1
            cy = t.currency or "USD"
            by_currency[cy] = by_currency.get(cy, 0) + (t.amount or 0)

        # --- Alerts ---
        alerts = db.query(Alert).filter(
            Alert.created_at >= start,
            Alert.created_at <= end,
        ).all()

        alert_total = len(alerts)
        alert_by_sev: Dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for a in alerts:
            sev = a.severity or "low"
            alert_by_sev[sev] = alert_by_sev.get(sev, 0) + 1

        alerts_closed = sum(1 for a in alerts if a.status in ("closed", "false_positive"))
        fp_count = sum(1 for a in alerts if a.status == "false_positive")

        # --- Cases ---
        cases = db.query(Case).filter(
            Case.created_at >= start,
            Case.created_at <= end,
        ).all()

        cases_total = len(cases)
        cases_closed = sum(1 for c in cases if c.status == "closed")
        sars_filed = sum(1 for c in cases if c.sar_filed)

        # --- Rule activity ---
        rules = db.query(Rule).all()
        rule_activity = []
        for rule in rules:
            rule_alerts = [a for a in alerts if a.rule_id == rule.id]
            if rule_alerts:
                rule_activity.append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "alert_count": len(rule_alerts),
                    "false_positives": sum(1 for a in rule_alerts if a.status == "false_positive"),
                })

        return {
            "report_type": "monthly_compliance",
            "period": f"{year}-{month:02d}",
            "generated_at": self._now().isoformat(),
            "transactions": {
                "total": txn_total,
                "total_volume_usd": round(txn_volume, 2),
                "flagged": txn_flagged,
                "flagged_pct": round(txn_flagged / txn_total * 100, 2) if txn_total > 0 else 0.0,
                "international": txn_intl,
                "by_type": by_type,
                "by_currency": {k: round(v, 2) for k, v in by_currency.items()},
            },
            "alerts": {
                "total": alert_total,
                "by_severity": alert_by_sev,
                "resolved": alerts_closed,
                "false_positives": fp_count,
                "fp_rate_pct": round(fp_count / alert_total * 100, 2) if alert_total > 0 else 0.0,
            },
            "cases": {
                "total": cases_total,
                "closed": cases_closed,
                "sars_filed": sars_filed,
                "sar_rate_pct": round(sars_filed / cases_total * 100, 2) if cases_total > 0 else 0.0,
            },
            "rule_activity": sorted(rule_activity, key=lambda x: x["alert_count"], reverse=True),
        }

    # ---------------------------------------------------------------------------
    # quarterly_report
    # ---------------------------------------------------------------------------

    def quarterly_report(self, db: Any, year: int, quarter: int) -> Dict[str, Any]:
        """
        Generate a quarterly compliance report by aggregating monthly reports.

        Args:
            db:      SQLAlchemy session.
            year:    Report year.
            quarter: Quarter number (1–4).

        Returns:
            Aggregated quarterly report dict.

        Raises:
            ValueError: If quarter is not 1–4.
        """
        if quarter not in (1, 2, 3, 4):
            raise ValueError(f"quarter must be 1–4, got {quarter}")

        first_month = (quarter - 1) * 3 + 1
        months = [first_month, first_month + 1, first_month + 2]
        monthly_reports = [self.monthly_report(db, year, m) for m in months]

        # Aggregate
        total_txns = sum(r["transactions"]["total"] for r in monthly_reports)
        total_volume = sum(r["transactions"]["total_volume_usd"] for r in monthly_reports)
        total_flagged = sum(r["transactions"]["flagged"] for r in monthly_reports)
        total_alerts = sum(r["alerts"]["total"] for r in monthly_reports)
        total_fp = sum(r["alerts"]["false_positives"] for r in monthly_reports)
        total_cases = sum(r["cases"]["total"] for r in monthly_reports)
        total_sars = sum(r["cases"]["sars_filed"] for r in monthly_reports)

        severity_totals: Dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for r in monthly_reports:
            for sev, cnt in r["alerts"]["by_severity"].items():
                severity_totals[sev] = severity_totals.get(sev, 0) + cnt

        return {
            "report_type": "quarterly_compliance",
            "period": f"Q{quarter} {year}",
            "months_included": [f"{year}-{m:02d}" for m in months],
            "generated_at": self._now().isoformat(),
            "transactions": {
                "total": total_txns,
                "total_volume_usd": round(total_volume, 2),
                "flagged": total_flagged,
                "flagged_pct": round(total_flagged / total_txns * 100, 2) if total_txns > 0 else 0.0,
            },
            "alerts": {
                "total": total_alerts,
                "by_severity": severity_totals,
                "false_positives": total_fp,
                "fp_rate_pct": round(total_fp / total_alerts * 100, 2) if total_alerts > 0 else 0.0,
            },
            "cases": {
                "total": total_cases,
                "sars_filed": total_sars,
                "sar_rate_pct": round(total_sars / total_cases * 100, 2) if total_cases > 0 else 0.0,
            },
            "monthly_breakdown": monthly_reports,
        }

    # ---------------------------------------------------------------------------
    # annual_report
    # ---------------------------------------------------------------------------

    def annual_report(self, db: Any, year: int) -> Dict[str, Any]:
        """
        Generate an annual compliance report by aggregating all four quarters.

        Args:
            db:   SQLAlchemy session.
            year: Report year (e.g. 2024).

        Returns:
            Annual report with quarterly breakdown and YoY indicators.
        """
        quarterly_reports = [self.quarterly_report(db, year, q) for q in range(1, 5)]

        total_txns = sum(r["transactions"]["total"] for r in quarterly_reports)
        total_volume = sum(r["transactions"]["total_volume_usd"] for r in quarterly_reports)
        total_flagged = sum(r["transactions"]["flagged"] for r in quarterly_reports)
        total_alerts = sum(r["alerts"]["total"] for r in quarterly_reports)
        total_fp = sum(r["alerts"]["false_positives"] for r in quarterly_reports)
        total_cases = sum(r["cases"]["total"] for r in quarterly_reports)
        total_sars = sum(r["cases"]["sars_filed"] for r in quarterly_reports)

        return {
            "report_type": "annual_compliance",
            "year": year,
            "generated_at": self._now().isoformat(),
            "summary": {
                "total_transactions": total_txns,
                "total_volume_usd": round(total_volume, 2),
                "total_flagged": total_flagged,
                "total_alerts": total_alerts,
                "total_cases": total_cases,
                "total_sars_filed": total_sars,
                "overall_fp_rate_pct": round(total_fp / total_alerts * 100, 2) if total_alerts > 0 else 0.0,
                "sar_filing_rate_pct": round(total_sars / total_cases * 100, 2) if total_cases > 0 else 0.0,
            },
            "quarterly_breakdown": quarterly_reports,
        }

    # ---------------------------------------------------------------------------
    # generate_executive_summary
    # ---------------------------------------------------------------------------

    def generate_executive_summary(self, db: Any, days: int = 30) -> Dict[str, Any]:
        """
        Generate a concise executive summary for the past N days.

        Suitable for C-suite or board-level reporting.

        Args:
            db:   SQLAlchemy session.
            days: Lookback window in days.

        Returns:
            Executive summary dict with key risk indicators.
        """
        from analysis.compliance_metrics import compliance_score, regulatory_breach_count
        from analysis.customer_risk_analysis import risk_distribution

        cutoff = self._now() - timedelta(days=days)

        from models.transaction import Transaction
        from models.alert import Alert
        from models.case import Case
        from models.customer import Customer

        txn_count = db.query(Transaction).filter(Transaction.created_at >= cutoff).count()
        alert_count = db.query(Alert).filter(Alert.created_at >= cutoff).count()
        case_count = db.query(Case).filter(Case.created_at >= cutoff).count()
        open_critical = db.query(Alert).filter(
            Alert.status == "open", Alert.severity == "critical"
        ).count()

        comp_score = compliance_score(db)
        breach_data = regulatory_breach_count(db, days=days)
        risk_dist = risk_distribution(db)

        return {
            "report_type": "executive_summary",
            "period_days": days,
            "generated_at": self._now().isoformat(),
            "headline_kpis": {
                "transactions_reviewed": txn_count,
                "alerts_generated": alert_count,
                "cases_opened": case_count,
                "open_critical_alerts": open_critical,
                "compliance_score": comp_score["overall_score"],
                "compliance_grade": comp_score["grade"],
                "regulatory_breaches": breach_data["total_breaches"],
            },
            "portfolio_risk": risk_dist,
            "compliance_health": comp_score,
            "top_concerns": self._identify_top_concerns(
                open_critical, breach_data, comp_score
            ),
        }

    def _identify_top_concerns(
        self,
        open_critical: int,
        breach_data: Dict,
        comp_score: Dict,
    ) -> List[str]:
        """Identify top compliance concerns from metrics."""
        concerns = []

        if open_critical > 5:
            concerns.append(f"{open_critical} critical alerts remain unresolved and need immediate attention.")

        if breach_data.get("stale_critical_alerts", 0) > 0:
            concerns.append(
                f"{breach_data['stale_critical_alerts']} critical alerts are overdue for resolution."
            )

        if breach_data.get("sanctioned_customers_with_open_alerts", 0) > 0:
            concerns.append(
                f"{breach_data['sanctioned_customers_with_open_alerts']} sanctioned customers "
                f"have open alerts requiring urgent review."
            )

        score = comp_score.get("overall_score", 100)
        if score < 70:
            concerns.append(
                f"Overall compliance score of {score:.1f}/100 is below acceptable threshold (70)."
            )

        kyc = comp_score.get("components", {}).get("kyc_coverage", {})
        if kyc.get("score", 100) < 80:
            concerns.append(
                f"KYC coverage score ({kyc.get('score', 0):.1f}/100) indicates incomplete customer data."
            )

        return concerns or ["No major compliance concerns identified at this time."]

    # ---------------------------------------------------------------------------
    # kpi_table
    # ---------------------------------------------------------------------------

    def kpi_table(self, db: Any, days: int = 30) -> List[Dict[str, Any]]:
        """
        Generate a flat table of KPIs for tabular display.

        Args:
            db:   SQLAlchemy session.
            days: Lookback period.

        Returns:
            List of KPI rows: [{kpi_name, value, unit, status, benchmark}]
        """
        from analysis.compliance_metrics import aml_kpi_summary
        kpis = aml_kpi_summary(db)

        rows = []

        sar_rate = kpis["sar_filing"]["sar_filing_rate_pct"]
        rows.append({
            "kpi_name": "SAR Filing Rate",
            "value": sar_rate,
            "unit": "%",
            "status": "ok" if sar_rate >= 10 else "warning",
            "benchmark": ">=10%",
        })

        sla = kpis["case_resolution_time"]["sla_72h_pct"]
        rows.append({
            "kpi_name": "Case Resolution SLA (72h)",
            "value": sla,
            "unit": "%",
            "status": "ok" if sla >= 80 else "warning",
            "benchmark": ">=80%",
        })

        fp = kpis["alert_to_case_conversion"].get("conversion_rate_pct", 0)
        rows.append({
            "kpi_name": "Alert-to-Case Conversion Rate",
            "value": fp,
            "unit": "%",
            "status": "ok" if fp >= 5 else "warning",
            "benchmark": ">=5%",
        })

        kyc_cov = kpis["kyc_coverage"]["fully_complete_pct"]
        rows.append({
            "kpi_name": "KYC Completeness",
            "value": kyc_cov,
            "unit": "%",
            "status": "ok" if kyc_cov >= 85 else "warning",
            "benchmark": ">=85%",
        })

        overall = kpis["compliance_score"]["overall_score"]
        rows.append({
            "kpi_name": "Overall Compliance Score",
            "value": overall,
            "unit": "/100",
            "status": "ok" if overall >= 70 else ("warning" if overall >= 50 else "critical"),
            "benchmark": ">=70",
        })

        return rows

    # ---------------------------------------------------------------------------
    # rule_performance_table
    # ---------------------------------------------------------------------------

    def rule_performance_table(self, db: Any) -> List[Dict[str, Any]]:
        """
        Generate a rule performance table showing effectiveness metrics per rule.

        Args:
            db: SQLAlchemy session.

        Returns:
            List of rule performance rows sorted by alert count descending.
        """
        from analysis.compliance_metrics import rule_effectiveness
        return rule_effectiveness(db)

    # ---------------------------------------------------------------------------
    # export_to_dict
    # ---------------------------------------------------------------------------

    def export_to_dict(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export a report dict with additional export metadata.

        Args:
            report: Any report dict generated by this class.

        Returns:
            Report dict with export_metadata appended.
        """
        return {
            **report,
            "export_metadata": {
                "exported_at": self._now().isoformat(),
                "exported_by": "ComplianceReportGenerator",
                "version": "1.0",
                "format": "dict",
            },
        }
