from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, func
from database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_number = Column(String, unique=True, nullable=False, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey("rules.id"), nullable=True)
    severity = Column(String, nullable=False)
    status = Column(String, default="open")
    reason = Column(String, nullable=False)
    details = Column(String, nullable=True)
    risk_score = Column(Float, default=0.0)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, onupdate=func.now())
    closed_at = Column(DateTime, nullable=True)
