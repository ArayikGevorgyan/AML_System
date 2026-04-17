"""
AML Pattern Recognition
=========================
Detects classic money laundering patterns in transaction sequences:
  - Smurfing (structuring below thresholds)
  - Layering (rapid multi-hop movement)
  - Integration (funds entering legitimate economy)
  - Rapid movement between accounts
  - Unusual counterparty networks

Usage:
    from ml.pattern_recognition import AMLPatternDetector

    detector = AMLPatternDetector()
    scores = detector.score_patterns(transactions)
    layering = detector.detect_layering(transactions, hops=3)
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
import statistics

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_STRUCTURING_THRESHOLD = 10000.0   # USD
DEFAULT_RAPID_HOURS = 24                   # hours for rapid movement detection
HIGH_RISK_COUNTRIES = {
    "IR", "KP", "SY", "CU", "RU", "BY", "MM", "YE",
    "LY", "SO", "SD", "ZW", "CD", "AF",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure a datetime is timezone-aware (UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class AMLPatternDetector:
    """
    Detects money laundering patterns from transaction sequences.

    Each detection method returns a structured result dict with detected
    pattern instances and a confidence score (0–100).
    """

    def __init__(self, structuring_threshold: float = DEFAULT_STRUCTURING_THRESHOLD) -> None:
        """
        Initialize the pattern detector.

        Args:
            structuring_threshold: Reporting threshold for structuring detection.
        """
        self.structuring_threshold = structuring_threshold

    # ---------------------------------------------------------------------------
    # detect_smurfing
    # ---------------------------------------------------------------------------

    def detect_smurfing(
        self,
        transactions: List[Any],
        threshold: Optional[float] = None,
        window_days: int = 3,
    ) -> Dict[str, Any]:
        """
        Detect smurfing: multiple deposits just below the reporting threshold
        that together exceed it within a short window.

        Args:
            transactions: List of Transaction objects sorted by created_at.
            threshold:    Override reporting threshold (default: self.structuring_threshold).
            window_days:  Days window to aggregate small transactions.

        Returns:
            Dict with:
                - pattern: "smurfing"
                - detected_instances: List of suspect groups
                - total_suspicious_amount: float
                - confidence_score: float (0–100)
        """
        threshold = threshold or self.structuring_threshold
        band_low = threshold * 0.70
        band_high = threshold * 0.99

        # Group candidate transactions by day
        by_day: Dict[str, List] = {}
        for t in transactions:
            amt = getattr(t, "amount", 0) or 0
            ca = _ensure_aware(getattr(t, "created_at", None))
            if band_low <= amt < band_high and ca:
                day_key = ca.strftime("%Y-%m-%d")
                if day_key not in by_day:
                    by_day[day_key] = []
                by_day[day_key].append(t)

        # Look for windows where multiple small txns combine above threshold
        suspect_groups = []
        total_suspicious = 0.0

        all_days = sorted(by_day.keys())
        for i, day in enumerate(all_days):
            # Aggregate over window_days
            window_txns = []
            for offset in range(window_days):
                from datetime import timedelta
                look_day = (datetime.strptime(day, "%Y-%m-%d") +
                            timedelta(days=offset)).strftime("%Y-%m-%d")
                window_txns.extend(by_day.get(look_day, []))

            if len(window_txns) >= 2:
                combined = sum(getattr(t, "amount", 0) or 0 for t in window_txns)
                if combined >= threshold:
                    group = {
                        "window_start": day,
                        "transaction_count": len(window_txns),
                        "total_amount": round(combined, 2),
                        "transaction_ids": [getattr(t, "id", None) for t in window_txns],
                        "individual_amounts": [
                            round(getattr(t, "amount", 0) or 0, 2) for t in window_txns
                        ],
                    }
                    suspect_groups.append(group)
                    total_suspicious += combined

        unique_groups = {g["window_start"]: g for g in suspect_groups}
        detected = list(unique_groups.values())

        # Score: more groups = higher confidence
        confidence = min(len(detected) * 25 + (total_suspicious / threshold) * 5, 100.0)

        return {
            "pattern": "smurfing",
            "detected_instances": detected[:20],
            "total_suspicious_amount": round(total_suspicious, 2),
            "confidence_score": round(confidence, 2),
        }

    # ---------------------------------------------------------------------------
    # detect_layering
    # ---------------------------------------------------------------------------

    def detect_layering(
        self,
        transactions: List[Any],
        hops: int = 3,
    ) -> Dict[str, Any]:
        """
        Detect layering: funds move through a chain of accounts in quick succession
        with amounts differing by less than 15% at each hop.

        Args:
            transactions: List of Transaction objects sorted by created_at.
            hops:         Minimum chain length to flag (default 3).

        Returns:
            Dict with:
                - pattern: "layering"
                - chains: List of detected chains
                - confidence_score: float
        """
        # Build recipient → sender mapping
        by_recipient: Dict[int, List] = {}
        for t in transactions:
            rid = getattr(t, "to_customer_id", None)
            if rid is not None:
                if rid not in by_recipient:
                    by_recipient[rid] = []
                by_recipient[rid].append(t)

        chains = []

        def extend_chain(chain: List, visited: set):
            last_txn = chain[-1]
            last_recipient = getattr(last_txn, "to_customer_id", None)
            if last_recipient is None or last_recipient in visited:
                if len(chain) >= hops:
                    chains.append(list(chain))
                return

            next_txns = by_recipient.get(last_recipient, [])
            for next_t in next_txns:
                next_ca = _ensure_aware(getattr(next_t, "created_at", None))
                last_ca = _ensure_aware(getattr(last_txn, "created_at", None))
                if next_ca and last_ca:
                    diff_hours = (next_ca - last_ca).total_seconds() / 3600
                    if diff_hours < 0 or diff_hours > 48:
                        continue

                last_amount = getattr(last_txn, "amount", 1) or 1
                next_amount = getattr(next_t, "amount", 0) or 0
                amount_diff_ratio = abs(next_amount - last_amount) / last_amount
                if amount_diff_ratio <= 0.20:
                    new_visited = visited | {last_recipient}
                    extend_chain(chain + [next_t], new_visited)

            if len(chain) >= hops and last_recipient not in visited:
                chains.append(list(chain))

        # Start chains from each transaction
        for txn in transactions[:100]:
            sender = getattr(txn, "from_customer_id", None)
            extend_chain([txn], {sender} if sender else set())

        # Deduplicate by first txn reference
        seen_refs = set()
        unique_chains = []
        for chain in chains:
            ref = getattr(chain[0], "reference", str(id(chain[0])))
            if ref not in seen_refs:
                seen_refs.add(ref)
                chain_info = {
                    "length": len(chain),
                    "total_amount": round(
                        sum(getattr(t, "amount", 0) or 0 for t in chain), 2
                    ),
                    "start_reference": getattr(chain[0], "reference", "N/A"),
                    "end_reference": getattr(chain[-1], "reference", "N/A"),
                    "customer_path": [
                        getattr(chain[0], "from_customer_id", None)
                    ] + [getattr(t, "to_customer_id", None) for t in chain],
                }
                unique_chains.append(chain_info)

        confidence = min(len(unique_chains) * 20, 100.0)

        return {
            "pattern": "layering",
            "chains": sorted(unique_chains, key=lambda x: x["length"], reverse=True)[:15],
            "confidence_score": round(confidence, 2),
            "min_hops_required": hops,
        }

    # ---------------------------------------------------------------------------
    # detect_integration
    # ---------------------------------------------------------------------------

    def detect_integration(self, transactions: List[Any]) -> Dict[str, Any]:
        """
        Detect integration: illicit funds re-entering the legitimate economy
        via high-value transfers to low-risk business entities or payroll.

        Indicators: large transfers to multiple payees, use of 'payment' type
        after prior flagged transactions, sudden increase in outbound wires.

        Args:
            transactions: List of Transaction objects.

        Returns:
            Dict with pattern analysis results.
        """
        if not transactions:
            return {"pattern": "integration", "indicators": [],
                    "confidence_score": 0.0, "flagged_txn_count": 0}

        flagged = [t for t in transactions if getattr(t, "flagged", False)]
        payments = [t for t in transactions
                    if getattr(t, "transaction_type", "") in ("payment", "wire")]

        # After flagged transactions, look for payment/wire out
        integration_events = []
        flagged_ids = {getattr(t, "id", 0) for t in flagged}

        for pay_t in payments:
            pay_ca = _ensure_aware(getattr(pay_t, "created_at", None))
            amt = getattr(pay_t, "amount", 0) or 0
            if amt < 5000:
                continue

            # Was there a flagged transaction in the 7 days before this payment?
            for flag_t in flagged:
                flag_ca = _ensure_aware(getattr(flag_t, "created_at", None))
                if pay_ca and flag_ca:
                    diff_days = (pay_ca - flag_ca).total_seconds() / 86400
                    if 0 < diff_days <= 7:
                        integration_events.append({
                            "payment_id": getattr(pay_t, "id", None),
                            "payment_amount": round(amt, 2),
                            "payment_type": getattr(pay_t, "transaction_type", ""),
                            "prior_flagged_id": getattr(flag_t, "id", None),
                            "days_after_flagged": round(diff_days, 1),
                        })
                        break

        confidence = min(len(integration_events) * 15 + len(flagged) * 5, 100.0)

        return {
            "pattern": "integration",
            "indicators": integration_events[:10],
            "confidence_score": round(confidence, 2),
            "flagged_txn_count": len(flagged),
            "payment_txn_count": len(payments),
        }

    # ---------------------------------------------------------------------------
    # detect_rapid_movement
    # ---------------------------------------------------------------------------

    def detect_rapid_movement(
        self,
        transactions: List[Any],
        hours: int = DEFAULT_RAPID_HOURS,
    ) -> Dict[str, Any]:
        """
        Detect rapid movement of funds: large amounts transferred within
        a short time window, suggesting pass-through behavior.

        Args:
            transactions: List of Transaction objects sorted by created_at.
            hours:        Time window in hours (default 24).

        Returns:
            Dict describing rapid movement clusters.
        """
        if not transactions:
            return {"pattern": "rapid_movement", "clusters": [],
                    "confidence_score": 0.0}

        clusters = []
        n = len(transactions)

        for i, txn in enumerate(transactions):
            ca_i = _ensure_aware(getattr(txn, "created_at", None))
            if not ca_i:
                continue

            cluster = [txn]
            cluster_end = ca_i + timedelta(hours=hours)

            for j in range(i + 1, n):
                ca_j = _ensure_aware(getattr(transactions[j], "created_at", None))
                if ca_j and ca_j <= cluster_end:
                    cluster.append(transactions[j])
                else:
                    break

            if len(cluster) >= 3:
                total_amt = sum(getattr(t, "amount", 0) or 0 for t in cluster)
                if total_amt >= self.structuring_threshold:
                    clusters.append({
                        "window_hours": hours,
                        "txn_count": len(cluster),
                        "total_amount": round(total_amt, 2),
                        "start_time": ca_i.isoformat(),
                        "transaction_ids": [getattr(t, "id", None) for t in cluster],
                    })

        confidence = min(len(clusters) * 20, 100.0)
        return {
            "pattern": "rapid_movement",
            "clusters": clusters[:10],
            "confidence_score": round(confidence, 2),
            "window_hours": hours,
        }

    # ---------------------------------------------------------------------------
    # detect_unusual_counterparties
    # ---------------------------------------------------------------------------

    def detect_unusual_counterparties(
        self,
        transactions: List[Any],
        customer_id: int,
    ) -> Dict[str, Any]:
        """
        Detect unusual counterparty patterns: transacting with many new
        or previously unseen counterparties in a short period.

        Args:
            transactions: List of Transaction objects for the customer.
            customer_id:  The customer whose transactions are being analyzed.

        Returns:
            Dict describing counterparty diversity anomalies.
        """
        if not transactions:
            return {"pattern": "unusual_counterparties", "anomalies": [],
                    "confidence_score": 0.0}

        # Collect counterparty IDs
        counterparties: Dict[int, List] = {}
        for t in transactions:
            from_id = getattr(t, "from_customer_id", None)
            to_id = getattr(t, "to_customer_id", None)

            counterparty = to_id if from_id == customer_id else from_id
            if counterparty and counterparty != customer_id:
                if counterparty not in counterparties:
                    counterparties[counterparty] = []
                counterparties[counterparty].append(t)

        # Flag cases with many unique counterparties
        unique_count = len(counterparties)
        one_time = sum(1 for txns in counterparties.values() if len(txns) == 1)

        anomalies = []
        if unique_count > 10:
            anomalies.append({
                "type": "high_counterparty_diversity",
                "unique_counterparties": unique_count,
                "one_time_counterparties": one_time,
            })

        if one_time > unique_count * 0.8 and unique_count >= 5:
            anomalies.append({
                "type": "mostly_one_time_counterparties",
                "fraction_one_time": round(one_time / unique_count, 2),
            })

        confidence = min(unique_count * 5 + one_time * 3, 100.0)

        return {
            "pattern": "unusual_counterparties",
            "unique_counterparties": unique_count,
            "one_time_counterparties": one_time,
            "anomalies": anomalies,
            "confidence_score": round(confidence, 2),
        }

    # ---------------------------------------------------------------------------
    # score_patterns
    # ---------------------------------------------------------------------------

    def score_patterns(self, transactions: List[Any]) -> Dict[str, float]:
        """
        Run all pattern detectors and return a dict of pattern → confidence scores.

        Args:
            transactions: List of Transaction objects.

        Returns:
            Dict[str, float] mapping each pattern name to its confidence score (0–100).
            Also includes a composite AML risk score.
        """
        if not transactions:
            return {
                "smurfing": 0.0,
                "layering": 0.0,
                "integration": 0.0,
                "rapid_movement": 0.0,
                "unusual_counterparties": 0.0,
                "composite_aml_score": 0.0,
            }

        customer_id = getattr(transactions[0], "from_customer_id", 0) or 0

        smurfing_result = self.detect_smurfing(transactions)
        layering_result = self.detect_layering(transactions)
        integration_result = self.detect_integration(transactions)
        rapid_result = self.detect_rapid_movement(transactions)
        counterparty_result = self.detect_unusual_counterparties(transactions, customer_id)

        scores = {
            "smurfing": smurfing_result["confidence_score"],
            "layering": layering_result["confidence_score"],
            "integration": integration_result["confidence_score"],
            "rapid_movement": rapid_result["confidence_score"],
            "unusual_counterparties": counterparty_result["confidence_score"],
        }

        # Composite: weighted average
        weights = {
            "smurfing": 0.25,
            "layering": 0.25,
            "integration": 0.20,
            "rapid_movement": 0.15,
            "unusual_counterparties": 0.15,
        }

        composite = sum(scores[p] * weights[p] for p in scores)
        scores["composite_aml_score"] = round(min(composite, 100.0), 2)

        return {k: round(v, 2) for k, v in scores.items()}
