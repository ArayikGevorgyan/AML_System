from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, BackgroundTasks

from models.transaction import Transaction
from models.account import Account
from models.user import User
from schemas.transaction import TransactionCreate, TransactionFilter
from services.rules_engine import rules_engine
from services.alert_service import alert_service
from services.audit_service import audit_service


def _generate_reference(db: Session) -> str:
    count = db.query(Transaction).count()
    today = datetime.now().strftime("%Y%m%d")
    return f"TXN-{today}-{count + 1:06d}"


class TransactionService:

    def create_transaction(
        self,
        data: TransactionCreate,
        db: Session,
        user: User,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> Transaction:
        # Validate accounts if provided
        if data.from_account_id:
            acc = db.query(Account).filter(Account.id == data.from_account_id).first()
            if not acc:
                raise HTTPException(status_code=404, detail="Source account not found")

        is_international = (
            data.originating_country is not None
            and data.destination_country is not None
            and data.originating_country != data.destination_country
        )

        txn = Transaction(
            reference=_generate_reference(db),
            from_account_id=data.from_account_id,
            to_account_id=data.to_account_id,
            from_customer_id=data.from_customer_id,
            to_customer_id=data.to_customer_id,
            amount=data.amount,
            currency=data.currency,
            transaction_type=data.transaction_type,
            description=data.description,
            originating_country=data.originating_country,
            destination_country=data.destination_country,
            is_international=is_international,
            channel=data.channel,
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)

        # Run rules engine synchronously or in background
        if background_tasks:
            background_tasks.add_task(self._run_rules, txn.id, db)
        else:
            self._run_rules_inline(txn, db)

        audit_service.log(
            db, action="CREATE_TRANSACTION", user=user,
            entity_type="transaction", entity_id=txn.id,
            new_value={"reference": txn.reference, "amount": txn.amount},
        )
        return txn

    def _run_rules_inline(self, txn: Transaction, db: Session):
        matches = rules_engine.evaluate(txn, db)
        if matches:
            alert_service.create_alerts_from_matches(matches, txn, db)

    def _run_rules(self, txn_id: int, db: Session):
        txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
        if txn:
            self._run_rules_inline(txn, db)

    def get_transaction(self, txn_id: int, db: Session) -> Transaction:
        txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
        if not txn:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return txn

    def list_transactions(self, filters: TransactionFilter, db: Session):
        query = db.query(Transaction)
        if filters.customer_id:
            query = query.filter(
                (Transaction.from_customer_id == filters.customer_id) |
                (Transaction.to_customer_id == filters.customer_id)
            )
        if filters.transaction_type:
            query = query.filter(Transaction.transaction_type == filters.transaction_type)
        if filters.status:
            query = query.filter(Transaction.status == filters.status)
        if filters.flagged is not None:
            query = query.filter(Transaction.flagged == filters.flagged)
        if filters.min_amount is not None:
            query = query.filter(Transaction.amount >= filters.min_amount)
        if filters.max_amount is not None:
            query = query.filter(Transaction.amount <= filters.max_amount)
        if filters.date_from:
            query = query.filter(Transaction.created_at >= filters.date_from)
        if filters.date_to:
            query = query.filter(Transaction.created_at <= filters.date_to)
        if filters.originating_country:
            query = query.filter(Transaction.originating_country == filters.originating_country)

        total = query.count()
        items = (
            query.order_by(Transaction.created_at.desc())
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
            .all()
        )
        return {"total": total, "page": filters.page, "page_size": filters.page_size, "items": items}


transaction_service = TransactionService()
