from datetime import date
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException

from models.customer import Customer
from models.account import Account
from models.user import User
from schemas.customer import CustomerCreate, CustomerUpdate, AccountCreate
from services.audit_service import audit_service


def _generate_customer_number(db: Session) -> str:
    count = db.query(Customer).count()
    return f"CUS-{count + 1:06d}"


def _generate_account_number(db: Session) -> str:
    count = db.query(Account).count()
    return f"ACC-{count + 1:010d}"


class CustomerService:

    def create_customer(self, data: CustomerCreate, db: Session, user: User) -> Customer:
        customer = Customer(
            customer_number=_generate_customer_number(db),
            full_name=data.full_name,
            email=data.email,
            phone=data.phone,
            date_of_birth=data.date_of_birth,
            nationality=data.nationality,
            id_type=data.id_type,
            id_number=data.id_number,
            address=data.address,
            country=data.country,
            risk_level=data.risk_level,
            pep_status=data.pep_status,
            occupation=data.occupation,
            annual_income=data.annual_income,
            source_of_funds=data.source_of_funds,
            created_by=user.id,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
        audit_service.log(
            db, action="CREATE_CUSTOMER", user=user,
            entity_type="customer", entity_id=customer.id,
            new_value={"full_name": customer.full_name, "risk_level": customer.risk_level},
        )
        return customer

    def get_customer(self, customer_id: int, db: Session) -> Customer:
        c = db.query(Customer).filter(Customer.id == customer_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="Customer not found")
        return c

    def list_customers(
        self,
        db: Session,
        risk_level: Optional[str] = None,
        pep_status: Optional[bool] = None,
        sanctions_flag: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ):
        query = db.query(Customer)
        if risk_level:
            query = query.filter(Customer.risk_level == risk_level)
        if pep_status is not None:
            query = query.filter(Customer.pep_status == pep_status)
        if sanctions_flag is not None:
            query = query.filter(Customer.sanctions_flag == sanctions_flag)
        if search:
            query = query.filter(
                Customer.full_name.ilike(f"%{search}%") |
                Customer.customer_number.ilike(f"%{search}%") |
                Customer.email.ilike(f"%{search}%")
            )
        total = query.count()
        items = query.order_by(Customer.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    def update_customer(self, customer_id: int, data: CustomerUpdate, db: Session, user: User) -> Customer:
        customer = self.get_customer(customer_id, db)
        old = {"risk_level": customer.risk_level}
        for key, val in data.model_dump(exclude_none=True).items():
            setattr(customer, key, val)
        db.commit()
        db.refresh(customer)
        audit_service.log(
            db, action="UPDATE_CUSTOMER", user=user,
            entity_type="customer", entity_id=customer_id,
            old_value=old, new_value={"risk_level": customer.risk_level},
        )
        return customer

    def get_customer_accounts(self, customer_id: int, db: Session) -> List[Account]:
        return db.query(Account).filter(Account.customer_id == customer_id).all()

    def create_account(self, data: AccountCreate, db: Session, user: User) -> Account:
        self.get_customer(data.customer_id, db)
        account = Account(
            account_number=_generate_account_number(db),
            customer_id=data.customer_id,
            account_type=data.account_type,
            currency=data.currency,
            balance=data.balance,
            opened_date=date.today(),
            country=data.country,
            iban=data.iban,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return account


customer_service = CustomerService()
