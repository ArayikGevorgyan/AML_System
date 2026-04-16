from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey, func
from database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_number = Column(String, unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    account_type = Column(String, default="checking")  # checking, savings, business, investment
    currency = Column(String(3), default="USD")
    balance = Column(Float, default=0.0)
    status = Column(String, default="active")          # active, frozen, closed, suspended
    opened_date = Column(Date, nullable=True)
    country = Column(String(2), nullable=True)
    iban = Column(String, nullable=True)
    swift_code = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
