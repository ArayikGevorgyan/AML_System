from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, func
from database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reference = Column(String, unique=True, nullable=False, index=True)
    from_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    to_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    from_customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    to_customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    transaction_type = Column(String, nullable=False)  # transfer, deposit, withdrawal, wire, payment, cash
    status = Column(String, default="completed")       # completed, pending, failed, reversed
    description = Column(String, nullable=True)
    originating_country = Column(String(2), nullable=True)
    destination_country = Column(String(2), nullable=True)
    is_international = Column(Boolean, default=False)
    channel = Column(String, nullable=True)            # online, branch, atm, mobile
    risk_score = Column(Float, default=0.0)
    flagged = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)
