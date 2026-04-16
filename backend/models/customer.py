from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Float, ForeignKey, func
from database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_number = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False, index=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    nationality = Column(String(2), nullable=True)
    id_type = Column(String, nullable=True)
    id_number = Column(String, nullable=True)
    address = Column(String, nullable=True)
    country = Column(String(2), nullable=True)
    risk_level = Column(String, default="low")       # low, medium, high, critical
    pep_status = Column(Boolean, default=False)       # Politically Exposed Person
    sanctions_flag = Column(Boolean, default=False)
    occupation = Column(String, nullable=True)
    annual_income = Column(Float, nullable=True)
    source_of_funds = Column(String, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
