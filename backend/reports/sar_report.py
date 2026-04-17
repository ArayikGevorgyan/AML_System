"""
SAR Report Generator
======================
Generates Suspicious Activity Report (SAR) documents from AML case data.
SAR is a regulatory filing required by FinCEN (USA) and equivalent bodies
in other jurisdictions when a financial institution suspects money laundering
or related financial crimes.

Usage:
    from reports.sar_report import SARReportGenerator
    from database import SessionLocal

    db = SessionLocal()
    generator = SARReportGenerator()
    report = generator.generate(db, case_id=42)
    json_str = generator.to_json(report)
    issues = generator.validate_completeness(report)
"""

import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional


class SARReportGenerator:
    """
    Generates SAR report data structures from AML case and alert data.

    A SAR contains:
      - Subject information (the customer under suspicion)
      - Transaction details (suspicious transactions)
      - Narrative description of suspicious activity
      - Filing institution information
      - Case metadata

    All generate() outputs are plain dicts — rendering to PDF/HTML
    is handled by the caller.
    """

    REQUIRED_FIELDS = [
        "subject.full_name",
        "subject.date_of_birth",
        "subject.id_type",
        "subject.id_number",
        "subject.address",
        "transactions.total_amount",
        "suspicious_activity.description",
        "filing.institution_name",
    ]

    def generate(self, db: Any, case_id: int) -> Dict[str, Any]:
        """
        Generate a complete SAR report for a given case ID.

        Pulls all relevant case, alert, customer, and transaction data
        from the database and assembles the SAR structure.

        Args:
            db:      SQLAlchemy session.
            case_id: ID of the case to generate a SAR for.

        Returns:
            SAR report as a dict with all required FinCEN-style fields.

        Raises:
            ValueError: If the case does not exist.
        """
        from models.case import Case, CaseNote
        from models.alert import Alert
        from models.customer import Customer
        from models.transaction import Transaction

        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case {case_id} not found.")

        # Load related alert
        alert = None
        if case.alert_id:
            alert = db.query(Alert).filter(Alert.id == case.alert_id).first()

        # Load customer
        customer = None
        if alert and alert.customer_id:
            customer = db.query(Customer).filter(Customer.id == alert.customer_id).first()

        # Load associated transactions
        transactions = []
        if customer:
            transactions = db.query(Transaction).filter(
                Transaction.from_customer_id == customer.id,
                Transaction.flagged == True,
            ).order_by(Transaction.created_at.desc()).limit(20).all()

        # Load case notes for narrative
        notes = db.query(CaseNote).filter(CaseNote.case_id == case_id).all()
        note_texts = [n.note for n in notes if n.note]

        # Build subject section
        subject = self._build_subject(customer)

        # Build transaction section
        txn_section = self._build_transaction_section(transactions)

        # Build narrative
        narrative = self.format_narrative(case, customer, alert, transactions)

        # Identify activity type
        activity_types = self._classify_activity(transactions, alert)

        report = {
            "sar_reference": case.sar_reference or f"SAR-{case.case_number}",
            "case_id": case_id,
            "case_number": case.case_number,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "filing": {
                "institution_name": "AML Monitoring System Demo Bank",
                "institution_type": "bank",
                "ein": "XX-XXXXXXX",
                "contact_name": "Compliance Officer",
                "contact_phone": "+1-800-000-0000",
                "filing_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "prior_sar": bool(case.sar_reference),
            },
            "subject": subject,
            "transactions": txn_section,
            "suspicious_activity": {
                "description": narrative,
                "activity_types": activity_types,
                "date_range_start": txn_section.get("date_range_start", ""),
                "date_range_end": txn_section.get("date_range_end", ""),
                "loss_to_institution": False,
                "amount_involved": txn_section.get("total_amount", 0.0),
            },
            "case_notes_summary": " | ".join(note_texts[:5]) if note_texts else "",
            "alert_summary": self._build_alert_summary(alert),
            "status": case.status,
            "priority": case.priority,
        }

        return report

    def _build_subject(self, customer: Optional[Any]) -> Dict[str, Any]:
        """
        Build the SAR subject section from a Customer ORM object.

        Args:
            customer: Customer ORM object, or None if unknown.

        Returns:
            Subject dict with personal information fields.
        """
        if not customer:
            return {
                "full_name": "Unknown",
                "date_of_birth": None,
                "nationality": None,
                "id_type": None,
                "id_number": None,
                "address": None,
                "phone": None,
                "email": None,
                "occupation": None,
                "source_of_funds": None,
                "risk_level": "unknown",
                "pep_status": False,
                "sanctions_flag": False,
                "customer_number": None,
            }

        return {
            "full_name": customer.full_name,
            "date_of_birth": str(customer.date_of_birth) if customer.date_of_birth else None,
            "nationality": customer.nationality,
            "country": customer.country,
            "id_type": customer.id_type,
            "id_number": customer.id_number,
            "address": customer.address,
            "phone": customer.phone,
            "email": customer.email,
            "occupation": customer.occupation,
            "source_of_funds": customer.source_of_funds,
            "annual_income": customer.annual_income,
            "risk_level": customer.risk_level,
            "pep_status": customer.pep_status,
            "sanctions_flag": customer.sanctions_flag,
            "customer_number": customer.customer_number,
        }

    def _build_transaction_section(self, transactions: List[Any]) -> Dict[str, Any]:
        """
        Build the transactions section for the SAR report.

        Args:
            transactions: List of Transaction ORM objects.

        Returns:
            Transaction summary dict.
        """
        if not transactions:
            return {
                "count": 0,
                "total_amount": 0.0,
                "currencies": [],
                "types": [],
                "date_range_start": None,
                "date_range_end": None,
                "items": [],
            }

        dates = [t.created_at for t in transactions if t.created_at]
        earliest = min(dates).strftime("%Y-%m-%d") if dates else None
        latest = max(dates).strftime("%Y-%m-%d") if dates else None

        total = sum(t.amount or 0 for t in transactions)
        currencies = list({t.currency for t in transactions if t.currency})
        types = list({t.transaction_type for t in transactions if t.transaction_type})

        items = [
            {
                "id": t.id,
                "reference": t.reference,
                "amount": t.amount,
                "currency": t.currency,
                "type": t.transaction_type,
                "date": t.created_at.strftime("%Y-%m-%d") if t.created_at else None,
                "is_international": t.is_international,
                "originating_country": t.originating_country,
                "destination_country": t.destination_country,
                "risk_score": t.risk_score,
            }
            for t in transactions[:20]
        ]

        return {
            "count": len(transactions),
            "total_amount": round(total, 2),
            "currencies": currencies,
            "types": types,
            "date_range_start": earliest,
            "date_range_end": latest,
            "items": items,
        }

    def _build_alert_summary(self, alert: Optional[Any]) -> Dict[str, Any]:
        """Build alert summary for SAR context section."""
        if not alert:
            return {}
        return {
            "alert_number": alert.alert_number,
            "severity": alert.severity,
            "reason": alert.reason,
            "risk_score": alert.risk_score,
            "status": alert.status,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
        }

    def _classify_activity(
        self,
        transactions: List[Any],
        alert: Optional[Any],
    ) -> List[str]:
        """
        Classify the type of suspicious activity based on transaction patterns.

        Returns:
            List of activity type strings.
        """
        types = []
        if not transactions:
            return ["Unknown suspicious activity"]

        amounts = [t.amount for t in transactions if t.amount]
        avg = sum(amounts) / len(amounts) if amounts else 0

        intl_count = sum(1 for t in transactions if t.is_international)
        if intl_count > 0:
            types.append("International wire transfers")

        # Structuring check
        threshold = 10000.0
        near_threshold = [a for a in amounts if threshold * 0.7 <= a < threshold]
        if len(near_threshold) >= 2:
            types.append("Possible structuring (smurfing)")

        cash_txns = [t for t in transactions if t.transaction_type == "cash"]
        if cash_txns:
            types.append("Suspicious cash activity")

        if alert and alert.severity in ("critical", "high"):
            types.append("High-risk transaction pattern")

        if not types:
            types.append("Unusual transaction behavior")

        return types

    def to_pdf_data(self, report: Dict[str, Any]) -> bytes:
        """
        Convert a SAR report dict to PDF-ready byte data.

        In a full implementation, this would use a PDF library (e.g. reportlab).
        Returns a JSON-encoded bytes object as a placeholder.

        Args:
            report: SAR report dict.

        Returns:
            Bytes representing the report data.
        """
        json_str = json.dumps(report, indent=2, default=str)
        return json_str.encode("utf-8")

    def to_json(self, report: Dict[str, Any]) -> str:
        """
        Serialize a SAR report dict to a JSON string.

        Args:
            report: SAR report dict.

        Returns:
            Pretty-printed JSON string.
        """
        return json.dumps(report, indent=2, ensure_ascii=False, default=str)

    def validate_completeness(self, report: Dict[str, Any]) -> List[str]:
        """
        Check a SAR report for missing required fields.

        Args:
            report: SAR report dict.

        Returns:
            List of missing field path strings. Empty list = complete.
        """
        missing = []

        def get_nested(d: dict, path: str) -> Any:
            parts = path.split(".")
            val = d
            for part in parts:
                if not isinstance(val, dict):
                    return None
                val = val.get(part)
            return val

        for field_path in self.REQUIRED_FIELDS:
            val = get_nested(report, field_path)
            if val is None or val == "" or val == 0:
                missing.append(field_path)

        return missing

    def format_narrative(
        self,
        case: Any,
        customer: Optional[Any],
        alert: Optional[Any],
        transactions: List[Any],
    ) -> str:
        """
        Generate a SAR narrative text describing the suspicious activity.

        Args:
            case:         Case ORM object.
            customer:     Customer ORM object (may be None).
            alert:        Alert ORM object (may be None).
            transactions: List of Transaction objects.

        Returns:
            Narrative string suitable for SAR form field.
        """
        customer_name = customer.full_name if customer else "Unknown customer"
        risk_level = customer.risk_level.upper() if customer else "UNKNOWN"
        pep_note = " (Politically Exposed Person)" if (customer and customer.pep_status) else ""
        sanc_note = " (SANCTIONS HIT)" if (customer and customer.sanctions_flag) else ""

        total_amount = sum(t.amount or 0 for t in transactions)
        txn_count = len(transactions)

        dates = [t.created_at for t in transactions if t.created_at]
        if dates:
            date_range = (
                f"between {min(dates).strftime('%Y-%m-%d')} "
                f"and {max(dates).strftime('%Y-%m-%d')}"
            )
        else:
            date_range = "over an unspecified period"

        alert_reason = (alert.reason if alert else case.description) or "Suspicious behavior detected"

        intl_note = ""
        intl_txns = [t for t in transactions if t.is_international]
        if intl_txns:
            countries = {t.destination_country for t in intl_txns if t.destination_country}
            intl_note = (
                f" {len(intl_txns)} of these transactions were international, "
                f"involving countries: {', '.join(sorted(countries))}."
            )

        narrative = (
            f"The subject, {customer_name}{pep_note}{sanc_note}, "
            f"is categorized as {risk_level} risk. "
            f"This SAR is filed in relation to case {case.case_number}. "
            f"The basis for this report is: {alert_reason}. "
            f"A total of {txn_count} suspicious transaction(s) totaling "
            f"${total_amount:,.2f} were identified {date_range}.{intl_note} "
            f"The institution has reviewed available documentation and, "
            f"based on the totality of circumstances, believes this activity "
            f"is inconsistent with the customer's known profile and may involve "
            f"money laundering, structuring, or related financial crime."
        )

        if case.resolution:
            narrative += f" Analyst notes: {case.resolution}"

        return narrative
