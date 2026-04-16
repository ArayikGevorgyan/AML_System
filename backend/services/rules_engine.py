import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from models.transaction import Transaction
from models.customer import Customer
from models.rule import Rule
from config import settings


@dataclass
class RuleMatch:
    rule_id: int
    rule_name: str
    category: str
    severity: str
    reason: str
    risk_score: float
    details: dict = field(default_factory=dict)


class RulesEngine:

    HIGH_RISK_COUNTRIES = set(settings.HIGH_RISK_COUNTRIES)

    def evaluate(self, transaction: Transaction, db: Session) -> List[RuleMatch]:
        active_rules: List[Rule] = db.query(Rule).filter(Rule.is_active == True).all()
        customer = db.query(Customer).filter(
            Customer.id == transaction.from_customer_id
        ).first()

        matches: List[RuleMatch] = []

        for rule in active_rules:
            match = self._evaluate_rule(rule, transaction, customer, db)
            if match:
                matches.append(match)

        return matches

    def _evaluate_rule(
        self,
        rule: Rule,
        txn: Transaction,
        customer: Optional[Customer],
        db: Session,
    ) -> Optional[RuleMatch]:
        dispatch = {
            "large_transaction": self._check_large_transaction,
            "structuring": self._check_structuring,
            "frequency": self._check_frequency,
            "velocity": self._check_velocity,
            "high_risk_country": self._check_high_risk_country,
            "rapid_movement": self._check_rapid_movement,
            "round_amount": self._check_round_amount,
            "pep_transaction": self._check_pep_transaction,
            "micro_transaction": self._check_micro_transaction,
        }
        handler = dispatch.get(rule.category)
        if handler:
            return handler(rule, txn, customer, db)
        return None

    def _check_large_transaction(
        self, rule: Rule, txn: Transaction, customer: Optional[Customer], db: Session
    ) -> Optional[RuleMatch]:
        threshold = rule.threshold_amount or settings.LARGE_TRANSACTION_THRESHOLD
        if txn.amount >= threshold:
            score = min(100.0, 50.0 + (txn.amount - threshold) / threshold * 30)
            return RuleMatch(
                rule_id=rule.id,
                rule_name=rule.name,
                category=rule.category,
                severity=rule.severity,
                reason=(
                    f"Transaction amount ${txn.amount:,.2f} exceeds "
                    f"large transaction threshold of ${threshold:,.2f}"
                ),
                risk_score=round(score, 2),
                details={
                    "amount": txn.amount,
                    "threshold": threshold,
                    "currency": txn.currency,
                },
            )
        return None

    def _check_structuring(
        self, rule: Rule, txn: Transaction, customer: Optional[Customer], db: Session
    ) -> Optional[RuleMatch]:
        threshold = rule.threshold_amount or settings.LARGE_TRANSACTION_THRESHOLD
        lower_bound = threshold * 0.80
        upper_bound = threshold * 0.999

        if lower_bound <= txn.amount <= upper_bound:
            window_hours = rule.time_window_hours or 72
            since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
            similar_count = db.query(func.count(Transaction.id)).filter(
                Transaction.from_customer_id == txn.from_customer_id,
                Transaction.amount.between(lower_bound, upper_bound),
                Transaction.created_at >= since,
                Transaction.id != txn.id,
            ).scalar() or 0

            score = min(95.0, 55.0 + similar_count * 8.0)
            return RuleMatch(
                rule_id=rule.id,
                rule_name=rule.name,
                category=rule.category,
                severity=rule.severity,
                reason=(
                    f"Potential structuring: amount ${txn.amount:,.2f} is just "
                    f"below reporting threshold. {similar_count} similar transactions "
                    f"in the past {window_hours}h."
                ),
                risk_score=round(score, 2),
                details={
                    "amount": txn.amount,
                    "threshold": threshold,
                    "similar_transactions_in_window": similar_count,
                    "window_hours": window_hours,
                },
            )
        return None

    def _check_frequency(
        self, rule: Rule, txn: Transaction, customer: Optional[Customer], db: Session
    ) -> Optional[RuleMatch]:
        window_hours = rule.time_window_hours or settings.VELOCITY_WINDOW_HOURS
        count_threshold = rule.threshold_count or settings.VELOCITY_COUNT_THRESHOLD
        since = datetime.now(timezone.utc) - timedelta(hours=window_hours)

        count = db.query(func.count(Transaction.id)).filter(
            Transaction.from_customer_id == txn.from_customer_id,
            Transaction.created_at >= since,
        ).scalar() or 0

        if count >= count_threshold:
            score = min(90.0, 50.0 + (count - count_threshold) * 5.0)
            return RuleMatch(
                rule_id=rule.id,
                rule_name=rule.name,
                category=rule.category,
                severity=rule.severity,
                reason=(
                    f"High transaction frequency: {count} transactions in "
                    f"the past {window_hours} hours (threshold: {count_threshold})"
                ),
                risk_score=round(score, 2),
                details={
                    "transaction_count": count,
                    "count_threshold": count_threshold,
                    "window_hours": window_hours,
                },
            )
        return None

    def _check_velocity(
        self, rule: Rule, txn: Transaction, customer: Optional[Customer], db: Session
    ) -> Optional[RuleMatch]:
        window_hours = rule.time_window_hours or 24
        amount_threshold = rule.threshold_amount or settings.VELOCITY_AMOUNT_THRESHOLD
        since = datetime.now(timezone.utc) - timedelta(hours=window_hours)

        total_volume = db.query(func.sum(Transaction.amount)).filter(
            Transaction.from_customer_id == txn.from_customer_id,
            Transaction.created_at >= since,
        ).scalar() or 0.0

        if total_volume >= amount_threshold:
            score = min(92.0, 55.0 + (total_volume - amount_threshold) / amount_threshold * 25)
            return RuleMatch(
                rule_id=rule.id,
                rule_name=rule.name,
                category=rule.category,
                severity=rule.severity,
                reason=(
                    f"High velocity: cumulative amount ${total_volume:,.2f} in "
                    f"{window_hours}h exceeds threshold of ${amount_threshold:,.2f}"
                ),
                risk_score=round(score, 2),
                details={
                    "total_volume_in_window": round(total_volume, 2),
                    "amount_threshold": amount_threshold,
                    "window_hours": window_hours,
                },
            )
        return None

    def _check_high_risk_country(
        self, rule: Rule, txn: Transaction, customer: Optional[Customer], db: Session
    ) -> Optional[RuleMatch]:
        risk_countries = set(settings.HIGH_RISK_COUNTRIES)
        if rule.high_risk_countries:
            try:
                extra = set(json.loads(rule.high_risk_countries))
                risk_countries = risk_countries.union(extra)
            except Exception:
                pass

        hit_countries = []
        if txn.originating_country and txn.originating_country.upper() in risk_countries:
            hit_countries.append(("originating", txn.originating_country))
        if txn.destination_country and txn.destination_country.upper() in risk_countries:
            hit_countries.append(("destination", txn.destination_country))
        if customer and customer.country and customer.country.upper() in risk_countries:
            hit_countries.append(("customer_country", customer.country))

        if hit_countries:
            score = 65.0 + len(hit_countries) * 10.0
            country_str = ", ".join(f"{role}={code}" for role, code in hit_countries)
            return RuleMatch(
                rule_id=rule.id,
                rule_name=rule.name,
                category=rule.category,
                severity=rule.severity,
                reason=f"Transaction involves high-risk country: {country_str}",
                risk_score=min(95.0, round(score, 2)),
                details={
                    "hit_countries": [{"role": r, "code": c} for r, c in hit_countries],
                    "amount": txn.amount,
                },
            )
        return None

    def _check_rapid_movement(
        self, rule: Rule, txn: Transaction, customer: Optional[Customer], db: Session
    ) -> Optional[RuleMatch]:
        window_hours = rule.time_window_hours or 24
        since = datetime.now(timezone.utc) - timedelta(hours=window_hours)

        incoming = db.query(func.sum(Transaction.amount)).filter(
            Transaction.to_customer_id == txn.from_customer_id,
            Transaction.transaction_type.in_(["deposit", "transfer", "wire"]),
            Transaction.created_at >= since,
        ).scalar() or 0.0

        outgoing = db.query(func.sum(Transaction.amount)).filter(
            Transaction.from_customer_id == txn.from_customer_id,
            Transaction.transaction_type.in_(["withdrawal", "transfer", "wire"]),
            Transaction.created_at >= since,
        ).scalar() or 0.0

        min_threshold = rule.threshold_amount or 5000.0
        if incoming >= min_threshold and outgoing >= min_threshold * 0.7:
            turnover_ratio = outgoing / incoming if incoming > 0 else 0
            score = min(90.0, 60.0 + turnover_ratio * 20.0)
            return RuleMatch(
                rule_id=rule.id,
                rule_name=rule.name,
                category=rule.category,
                severity=rule.severity,
                reason=(
                    f"Rapid fund movement: received ${incoming:,.2f} and sent "
                    f"${outgoing:,.2f} within {window_hours}h (turnover ratio: "
                    f"{turnover_ratio:.0%})"
                ),
                risk_score=round(score, 2),
                details={
                    "incoming_total": round(incoming, 2),
                    "outgoing_total": round(outgoing, 2),
                    "turnover_ratio": round(turnover_ratio, 3),
                    "window_hours": window_hours,
                },
            )
        return None

    def _check_round_amount(
        self, rule: Rule, txn: Transaction, customer: Optional[Customer], db: Session
    ) -> Optional[RuleMatch]:
        threshold = rule.threshold_amount or 1000.0
        if txn.amount < threshold:
            return None

        is_round = (txn.amount % 1000 == 0) or (
            txn.amount % 500 == 0 and txn.amount >= 5000
        )
        cents = txn.amount - int(txn.amount)
        has_no_cents = cents < 0.01

        if is_round and has_no_cents:
            window_hours = rule.time_window_hours or 48
            since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
            round_count = db.query(func.count(Transaction.id)).filter(
                Transaction.from_customer_id == txn.from_customer_id,
                Transaction.amount >= threshold,
                Transaction.created_at >= since,
                Transaction.id != txn.id,
            ).scalar() or 0

            if round_count >= 1 or txn.amount >= 10000:
                score = 45.0 + round_count * 5.0
                if txn.amount >= 10000:
                    score += 15.0
                return RuleMatch(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    category=rule.category,
                    severity=rule.severity,
                    reason=(
                        f"Suspicious round-number transaction: ${txn.amount:,.2f}. "
                        f"{round_count} similar round amounts in past {window_hours}h."
                    ),
                    risk_score=min(85.0, round(score, 2)),
                    details={
                        "amount": txn.amount,
                        "round_transactions_in_window": round_count,
                    },
                )
        return None

    def _check_pep_transaction(
        self, rule: Rule, txn: Transaction, customer: Optional[Customer], db: Session
    ) -> Optional[RuleMatch]:
        if not customer:
            return None
        threshold = rule.threshold_amount or 0.0
        if customer.pep_status and txn.amount >= threshold:
            score = 70.0 + (txn.amount / 10000) * 5.0
            return RuleMatch(
                rule_id=rule.id,
                rule_name=rule.name,
                category=rule.category,
                severity=rule.severity,
                reason=(
                    f"Transaction of ${txn.amount:,.2f} involves a "
                    f"Politically Exposed Person (PEP): {customer.full_name}"
                ),
                risk_score=min(95.0, round(score, 2)),
                details={
                    "customer_name": customer.full_name,
                    "pep_status": True,
                    "amount": txn.amount,
                },
            )
        return None

    def _check_micro_transaction(
        self, rule: Rule, txn: Transaction, customer: Optional[Customer], db: Session
    ) -> Optional[RuleMatch]:
        max_micro_amount = rule.threshold_amount or 100.0
        min_count        = rule.threshold_count  or 4
        window_hours     = rule.time_window_hours or 1

        if txn.amount > max_micro_amount:
            return None

        since = datetime.now(timezone.utc) - timedelta(hours=window_hours)

        micro_txns = (
            db.query(Transaction.created_at)
            .filter(
                Transaction.from_customer_id == txn.from_customer_id,
                Transaction.amount <= max_micro_amount,
                Transaction.created_at >= since,
            )
            .order_by(Transaction.created_at.asc())
            .all()
        )

        count = len(micro_txns)
        if count < min_count:
            return None

        if count >= 2:
            timestamps = [row[0] for row in micro_txns]
            tz_timestamps = []
            for ts in timestamps:
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                tz_timestamps.append(ts)
            intervals = [
                (tz_timestamps[i + 1] - tz_timestamps[i]).total_seconds() / 60
                for i in range(len(tz_timestamps) - 1)
            ]
            avg_interval_minutes = sum(intervals) / len(intervals)
        else:
            avg_interval_minutes = 0.0

        interval_threshold_minutes = 30.0
        if avg_interval_minutes > interval_threshold_minutes:
            return None

        score = min(88.0, 50.0 + count * 5.0 + max(0, (interval_threshold_minutes - avg_interval_minutes)) * 0.5)

        return RuleMatch(
            rule_id=rule.id,
            rule_name=rule.name,
            category=rule.category,
            severity=rule.severity,
            reason=(
                f"Micro-transaction pattern detected: {count} transactions of "
                f"≤${max_micro_amount:,.2f} in {window_hours}h with an average "
                f"interval of {avg_interval_minutes:.1f} min. "
                f"Possible automated account testing or micro-layering."
            ),
            risk_score=round(score, 2),
            details={
                "micro_transaction_count": count,
                "max_micro_amount": max_micro_amount,
                "avg_interval_minutes": round(avg_interval_minutes, 2),
                "window_hours": window_hours,
                "current_amount": txn.amount,
            },
        )


rules_engine = RulesEngine()
