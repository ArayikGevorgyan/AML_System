from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, func
from database import Base


class Rule(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    category = Column(String, nullable=False)
    threshold_amount = Column(Float, nullable=True)
    threshold_count = Column(Integer, nullable=True)
    time_window_hours = Column(Integer, nullable=True)
    high_risk_countries = Column(String, nullable=True)
    severity = Column(String, default="medium")
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
