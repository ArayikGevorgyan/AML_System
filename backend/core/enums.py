from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    SUPERVISOR = "supervisor"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    CLOSED = "closed"
    FALSE_POSITIVE = "false_positive"
    ESCALATED = "escalated"


class CaseStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    PENDING_REVIEW = "pending_review"
    ESCALATED = "escalated"
    CLOSED = "closed"
    FILED_SAR = "filed_sar"


class TransactionType(str, Enum):
    TRANSFER = "transfer"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    WIRE = "wire"
    PAYMENT = "payment"
    CASH = "cash"


class RuleCategory(str, Enum):
    LARGE_TRANSACTION = "large_transaction"
    FREQUENCY = "frequency"
    HIGH_RISK_COUNTRY = "high_risk_country"
    STRUCTURING = "structuring"
    VELOCITY = "velocity"
    RAPID_MOVEMENT = "rapid_movement"
    ROUND_AMOUNT = "round_amount"
    PEP_TRANSACTION = "pep_transaction"
    MICRO_TRANSACTION = "micro_transaction"


class AuditAction(str, Enum):
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    CREATE_CUSTOMER = "CREATE_CUSTOMER"
    UPDATE_CUSTOMER = "UPDATE_CUSTOMER"
    CREATE_TRANSACTION = "CREATE_TRANSACTION"
    CREATE_ALERT = "CREATE_ALERT"
    UPDATE_ALERT = "UPDATE_ALERT"
    CREATE_CASE = "CREATE_CASE"
    UPDATE_CASE = "UPDATE_CASE"
    ADD_CASE_NOTE = "ADD_CASE_NOTE"
    SANCTIONS_SEARCH = "SANCTIONS_SEARCH"
    IMPORT_SDN = "IMPORT_SDN"
    CREATE_RULE = "CREATE_RULE"
    UPDATE_RULE = "UPDATE_RULE"
    CREATE_USER = "CREATE_USER"
    UPDATE_USER = "UPDATE_USER"
