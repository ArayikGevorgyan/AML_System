from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class KPIStats(BaseModel):
    total_transactions_today: int
    total_transactions_month: int
    total_volume_today: float
    total_volume_month: float
    open_alerts: int
    high_critical_alerts: int
    open_cases: int
    high_risk_customers: int
    sanctions_checks_today: int
    flagged_transactions_today: int


class AlertsBySeverity(BaseModel):
    low: int
    medium: int
    high: int
    critical: int


class TransactionTimeSeries(BaseModel):
    dates: List[str]
    amounts: List[float]
    counts: List[int]


class AlertsTimeSeries(BaseModel):
    dates: List[str]
    counts: List[int]


class TopRuleTriggered(BaseModel):
    rule_name: str
    count: int
    severity: str


class RecentAlert(BaseModel):
    id: int
    alert_number: str
    customer_name: str
    severity: str
    status: str
    reason: str
    created_at: str


class DashboardResponse(BaseModel):
    kpis: KPIStats
    alerts_by_severity: AlertsBySeverity
    transaction_series: TransactionTimeSeries
    alerts_series: AlertsTimeSeries
    top_rules: List[TopRuleTriggered]
    recent_alerts: List[RecentAlert]
    cases_by_status: Dict[str, int]
