"""
Transaction Analysis
======================
Provides statistical analysis of transaction data for compliance reporting,
trend detection, and anomaly identification at the population level.

Unlike the per-transaction rules engine, this module analyses the entire
transaction dataset to surface macro-level patterns — e.g. which hour of
the day has the most flagged transactions, which country pairs are highest
risk, and how transaction volumes trend over time.

Usage:
    from database import SessionLocal
    from analysis.transaction_analysis import TransactionAnalyzer

    db = SessionLocal()
    analyzer = TransactionAnalyzer(db)

    print(analyzer.flagged_rate_by_type())
    print(analyzer.volume_trend(days=30))
    print(analyzer.top_risky_country_pairs(limit=10))
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from collections import defaultdict


class TransactionAnalyzer:
    """
    Statistical analysis engine for AML transaction data.

    All methods query the database lazily — no data is loaded until
    a method is called. Results are returned as plain dicts/lists
    suitable for JSON serialization.
    """

    def __init__(self, db):
        self.db = db

    # ── Volume & Trend ─────────────────────────────────────────────────

    def volume_trend(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Daily transaction count and total volume for the last N days.
        Useful for detecting sudden spikes or drops in activity.

        Returns list of dicts: [{date, count, total_amount, flagged_count}]
        """
        from models.transaction import Transaction
        from sqlalchemy import func, cast, Date

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        rows = (
            self.db.query(
                func.date(Transaction.created_at).label("date"),
                func.count(Transaction.id).label("count"),
                func.sum(Transaction.amount).label("total_amount"),
                func.sum(
                    func.cast(Transaction.flagged, type_=func.count(Transaction.id).type)
                ).label("flagged_count"),
            )
            .filter(Transaction.created_at >= cutoff)
            .group_by(func.date(Transaction.created_at))
            .order_by(func.date(Transaction.created_at))
            .all()
        )

        return [
            {
                "date":          str(row.date),
                "count":         row.count,
                "total_amount":  round(float(row.total_amount or 0), 2),
                "flagged_count": int(row.flagged_count or 0),
                "flag_rate":     round(int(row.flagged_count or 0) / row.count * 100, 2) if row.count else 0,
            }
            for row in rows
        ]

    def hourly_distribution(self) -> List[Dict[str, Any]]:
        """
        Transaction count and average amount by hour of day (0–23).
        Identifies off-hours activity which may indicate automated fraud.

        Returns list of 24 dicts: [{hour, count, avg_amount, flagged_count}]
        """
        from models.transaction import Transaction
        from sqlalchemy import func

        rows = (
            self.db.query(
                func.strftime("%H", Transaction.created_at).label("hour"),
                func.count(Transaction.id).label("count"),
                func.avg(Transaction.amount).label("avg_amount"),
                func.sum(
                    func.cast(Transaction.flagged, type_=func.count(Transaction.id).type)
                ).label("flagged_count"),
            )
            .group_by(func.strftime("%H", Transaction.created_at))
            .order_by("hour")
            .all()
        )

        return [
            {
                "hour":          int(row.hour) if row.hour else 0,
                "count":         row.count,
                "avg_amount":    round(float(row.avg_amount or 0), 2),
                "flagged_count": int(row.flagged_count or 0),
            }
            for row in rows
        ]

    # ── Flagging & Risk ────────────────────────────────────────────────

    def flagged_rate_by_type(self) -> List[Dict[str, Any]]:
        """
        Flagged transaction rate by transaction type.
        Identifies which transaction types are most associated with alerts.

        Returns list of dicts: [{type, total, flagged, flag_rate_pct}]
        """
        from models.transaction import Transaction
        from sqlalchemy import func

        rows = (
            self.db.query(
                Transaction.transaction_type,
                func.count(Transaction.id).label("total"),
                func.sum(
                    func.cast(Transaction.flagged, type_=func.count(Transaction.id).type)
                ).label("flagged"),
            )
            .group_by(Transaction.transaction_type)
            .order_by(func.count(Transaction.id).desc())
            .all()
        )

        results = []
        for row in rows:
            flagged = int(row.flagged or 0)
            total   = row.total
            results.append({
                "type":          row.transaction_type or "unknown",
                "total":         total,
                "flagged":       flagged,
                "flag_rate_pct": round(flagged / total * 100, 2) if total else 0,
            })
        return results

    def amount_distribution(self, buckets: Optional[List[float]] = None) -> List[Dict[str, Any]]:
        """
        Transaction count by amount bucket.
        Useful for detecting structuring (many transactions just below thresholds).

        Default buckets (USD): <1k, 1k-5k, 5k-10k, 10k-50k, 50k-100k, >100k
        """
        from models.transaction import Transaction

        if buckets is None:
            buckets = [0, 1_000, 5_000, 10_000, 50_000, 100_000, float("inf")]

        all_amounts = [
            float(row[0])
            for row in self.db.query(Transaction.amount).all()
        ]

        result = []
        for i in range(len(buckets) - 1):
            low  = buckets[i]
            high = buckets[i + 1]
            count = sum(1 for a in all_amounts if low <= a < high)
            label = (
                f"${low:,.0f}–${high:,.0f}"
                if high != float("inf")
                else f">${low:,.0f}"
            )
            result.append({"bucket": label, "count": count, "low": low, "high": high})

        return result

    # ── Geographic ────────────────────────────────────────────────────

    def top_risky_country_pairs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Top N country pairs (originating → destination) by flagged count.
        Surfaces the most suspicious international transfer corridors.
        """
        from models.transaction import Transaction
        from sqlalchemy import func

        rows = (
            self.db.query(
                Transaction.originating_country,
                Transaction.destination_country,
                func.count(Transaction.id).label("total"),
                func.sum(
                    func.cast(Transaction.flagged, type_=func.count(Transaction.id).type)
                ).label("flagged"),
                func.sum(Transaction.amount).label("total_amount"),
            )
            .filter(
                Transaction.originating_country.isnot(None),
                Transaction.destination_country.isnot(None),
                Transaction.originating_country != Transaction.destination_country,
            )
            .group_by(Transaction.originating_country, Transaction.destination_country)
            .order_by(func.sum(
                func.cast(Transaction.flagged, type_=func.count(Transaction.id).type)
            ).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "from":          row.originating_country,
                "to":            row.destination_country,
                "corridor":      f"{row.originating_country} → {row.destination_country}",
                "total":         row.total,
                "flagged":       int(row.flagged or 0),
                "total_amount":  round(float(row.total_amount or 0), 2),
                "flag_rate_pct": round(int(row.flagged or 0) / row.total * 100, 2) if row.total else 0,
            }
            for row in rows
        ]

    def transactions_by_country(self) -> List[Dict[str, Any]]:
        """
        Total transaction count and volume originating from each country.
        """
        from models.transaction import Transaction
        from sqlalchemy import func

        rows = (
            self.db.query(
                Transaction.originating_country,
                func.count(Transaction.id).label("count"),
                func.sum(Transaction.amount).label("total_amount"),
                func.avg(Transaction.amount).label("avg_amount"),
            )
            .filter(Transaction.originating_country.isnot(None))
            .group_by(Transaction.originating_country)
            .order_by(func.count(Transaction.id).desc())
            .all()
        )

        return [
            {
                "country":      row.originating_country,
                "count":        row.count,
                "total_amount": round(float(row.total_amount or 0), 2),
                "avg_amount":   round(float(row.avg_amount or 0), 2),
            }
            for row in rows
        ]

    # ── Summary ───────────────────────────────────────────────────────

    def summary_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        High-level transaction summary for the last N days.
        Suitable for dashboard widgets and executive reports.
        """
        from models.transaction import Transaction
        from sqlalchemy import func

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        total = self.db.query(func.count(Transaction.id)).filter(
            Transaction.created_at >= cutoff
        ).scalar() or 0

        flagged = self.db.query(func.count(Transaction.id)).filter(
            Transaction.created_at >= cutoff,
            Transaction.flagged == True,
        ).scalar() or 0

        volume = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.created_at >= cutoff
        ).scalar() or 0.0

        avg_amount = self.db.query(func.avg(Transaction.amount)).filter(
            Transaction.created_at >= cutoff
        ).scalar() or 0.0

        intl = self.db.query(func.count(Transaction.id)).filter(
            Transaction.created_at >= cutoff,
            Transaction.is_international == True,
        ).scalar() or 0

        return {
            "period_days":        days,
            "total_transactions": total,
            "flagged_count":      flagged,
            "flag_rate_pct":      round(flagged / total * 100, 2) if total else 0,
            "total_volume_usd":   round(float(volume), 2),
            "avg_amount_usd":     round(float(avg_amount), 2),
            "international_count": intl,
            "intl_rate_pct":      round(intl / total * 100, 2) if total else 0,
        }
