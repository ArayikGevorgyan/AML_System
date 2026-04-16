"""
Customer Risk Distribution Analysis
=======================================
Analyses the distribution of risk scores and risk levels across all customers.
Used to understand portfolio-level risk exposure, track risk score changes
over time, and identify concentrations of high-risk customers.

Usage:
    from database import SessionLocal
    from analysis.risk_distribution import RiskDistributionAnalyzer

    db = SessionLocal()
    analyzer = RiskDistributionAnalyzer(db)

    print(analyzer.risk_level_breakdown())
    print(analyzer.pep_and_sanctions_summary())
    print(analyzer.risk_by_country(limit=15))
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional


class RiskDistributionAnalyzer:
    """
    Analyses customer risk distribution across the portfolio.
    """

    def __init__(self, db):
        self.db = db

    # ── Risk Level Distribution ────────────────────────────────────────

    def risk_level_breakdown(self) -> Dict[str, Any]:
        """
        Count and percentage of customers at each risk level.
        Shows overall portfolio risk composition.

        Returns: {low, medium, high, critical, total, high_risk_pct}
        """
        from models.customer import Customer
        from sqlalchemy import func

        total = self.db.query(func.count(Customer.id)).scalar() or 0
        if total == 0:
            return {"total": 0, "low": 0, "medium": 0, "high": 0, "critical": 0}

        breakdown = {}
        for level in ("low", "medium", "high", "critical"):
            count = self.db.query(func.count(Customer.id)).filter(
                Customer.risk_level == level
            ).scalar() or 0
            breakdown[level] = {
                "count":   count,
                "pct":     round(count / total * 100, 2),
            }

        high_risk_total = breakdown["high"]["count"] + breakdown["critical"]["count"]

        return {
            "total":         total,
            "breakdown":     breakdown,
            "high_risk_count": high_risk_total,
            "high_risk_pct": round(high_risk_total / total * 100, 2),
        }

    def risk_level_trend(self, months: int = 6) -> List[Dict[str, Any]]:
        """
        Monthly count of new high/critical risk customers over the last N months.
        Detects if risk is growing in the portfolio.
        """
        from models.customer import Customer
        from sqlalchemy import func

        results = []
        now = datetime.now(timezone.utc)

        for i in range(months - 1, -1, -1):
            month_start = (now.replace(day=1) - timedelta(days=i * 30)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            month_end = (month_start + timedelta(days=32)).replace(day=1)

            high_count = self.db.query(func.count(Customer.id)).filter(
                Customer.risk_level.in_(["high", "critical"]),
                Customer.created_at >= month_start,
                Customer.created_at < month_end,
            ).scalar() or 0

            total_new = self.db.query(func.count(Customer.id)).filter(
                Customer.created_at >= month_start,
                Customer.created_at < month_end,
            ).scalar() or 0

            results.append({
                "month":           month_start.strftime("%Y-%m"),
                "new_customers":   total_new,
                "new_high_risk":   high_count,
                "high_risk_rate":  round(high_count / total_new * 100, 2) if total_new else 0,
            })

        return results

    # ── PEP & Sanctions ────────────────────────────────────────────────

    def pep_and_sanctions_summary(self) -> Dict[str, Any]:
        """
        Summary of PEP and sanctioned customer counts and their overlap.
        Critical for understanding the highest-risk customer segments.
        """
        from models.customer import Customer
        from sqlalchemy import func

        total       = self.db.query(func.count(Customer.id)).scalar() or 0
        pep         = self.db.query(func.count(Customer.id)).filter(Customer.pep_status == True).scalar() or 0
        sanctioned  = self.db.query(func.count(Customer.id)).filter(Customer.sanctions_flag == True).scalar() or 0
        pep_and_sanctioned = self.db.query(func.count(Customer.id)).filter(
            Customer.pep_status == True,
            Customer.sanctions_flag == True,
        ).scalar() or 0

        pep_high_risk = self.db.query(func.count(Customer.id)).filter(
            Customer.pep_status == True,
            Customer.risk_level.in_(["high", "critical"]),
        ).scalar() or 0

        return {
            "total_customers":       total,
            "pep_count":             pep,
            "pep_pct":               round(pep / total * 100, 2) if total else 0,
            "sanctioned_count":      sanctioned,
            "sanctioned_pct":        round(sanctioned / total * 100, 2) if total else 0,
            "pep_and_sanctioned":    pep_and_sanctioned,
            "pep_high_risk_count":   pep_high_risk,
        }

    # ── Geographic Risk ────────────────────────────────────────────────

    def risk_by_country(self, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Top N countries by high/critical risk customer count.
        Shows where portfolio risk is geographically concentrated.
        """
        from models.customer import Customer
        from sqlalchemy import func

        rows = (
            self.db.query(
                Customer.country,
                func.count(Customer.id).label("total"),
                func.sum(
                    func.cast(
                        Customer.risk_level.in_(["high", "critical"]),
                        type_=func.count(Customer.id).type
                    )
                ).label("high_risk"),
                func.sum(
                    func.cast(Customer.pep_status, type_=func.count(Customer.id).type)
                ).label("pep_count"),
            )
            .filter(Customer.country.isnot(None))
            .group_by(Customer.country)
            .order_by(func.count(Customer.id).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "country":       row.country,
                "total":         row.total,
                "high_risk":     int(row.high_risk or 0),
                "pep_count":     int(row.pep_count or 0),
                "high_risk_pct": round(int(row.high_risk or 0) / row.total * 100, 2) if row.total else 0,
            }
            for row in rows
        ]

    def risk_by_occupation(self) -> List[Dict[str, Any]]:
        """
        Average risk level and high-risk count by customer occupation.
        Identifies occupations that correlate with higher AML risk.
        """
        from models.customer import Customer
        from sqlalchemy import func

        risk_map = {"low": 0, "medium": 1, "high": 2, "critical": 3}

        rows = (
            self.db.query(
                Customer.occupation,
                func.count(Customer.id).label("count"),
            )
            .filter(Customer.occupation.isnot(None))
            .group_by(Customer.occupation)
            .order_by(func.count(Customer.id).desc())
            .limit(20)
            .all()
        )

        results = []
        for row in rows:
            if not row.occupation:
                continue
            customers = self.db.query(Customer).filter(
                Customer.occupation == row.occupation
            ).all()

            levels = [risk_map.get(c.risk_level, 0) for c in customers]
            avg_level = sum(levels) / len(levels) if levels else 0
            high_risk = sum(1 for c in customers if c.risk_level in ("high", "critical"))

            results.append({
                "occupation":    row.occupation,
                "count":         row.count,
                "avg_risk_score": round(avg_level, 2),
                "high_risk_count": high_risk,
                "high_risk_pct":  round(high_risk / row.count * 100, 2) if row.count else 0,
            })

        results.sort(key=lambda x: x["high_risk_pct"], reverse=True)
        return results

    # ── Alert Correlation ──────────────────────────────────────────────

    def alert_to_risk_correlation(self) -> List[Dict[str, Any]]:
        """
        For each risk level, shows the average number of alerts per customer.
        Validates that higher risk levels have proportionally more alerts.
        """
        from models.customer import Customer
        from models.alert import Alert
        from sqlalchemy import func

        results = []
        for level in ("low", "medium", "high", "critical"):
            customers = self.db.query(Customer).filter(
                Customer.risk_level == level
            ).all()

            if not customers:
                results.append({
                    "risk_level": level,
                    "customer_count": 0,
                    "avg_alerts": 0,
                    "total_alerts": 0,
                })
                continue

            total_alerts = 0
            for c in customers:
                count = self.db.query(func.count(Alert.id)).filter(
                    Alert.customer_id == c.id
                ).scalar() or 0
                total_alerts += count

            results.append({
                "risk_level":     level,
                "customer_count": len(customers),
                "total_alerts":   total_alerts,
                "avg_alerts":     round(total_alerts / len(customers), 2),
            })

        return results

    # ── Full Report ────────────────────────────────────────────────────

    def full_report(self) -> Dict[str, Any]:
        """Generate complete risk distribution report."""
        return {
            "generated_at":        datetime.now(timezone.utc).isoformat(),
            "risk_level_breakdown": self.risk_level_breakdown(),
            "pep_and_sanctions":   self.pep_and_sanctions_summary(),
            "risk_by_country":     self.risk_by_country(),
            "alert_correlation":   self.alert_to_risk_correlation(),
        }
