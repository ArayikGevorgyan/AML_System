"""
Daily Data Generator
====================
Automatically adds today's transactions and alerts.
Designed to be run by a cron job every 24 hours.
Run from backend/: python scripts/seed_today.py
"""

import sys
import random
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models.customer import Customer
from models.account import Account
from models.transaction import Transaction
from services.rules_engine import rules_engine
from services.alert_service import alert_service

random.seed()


def seed_today():
    db = SessionLocal()
    try:
        customers = db.query(Customer).all()
        accounts = db.query(Account).all()

        if not customers or not accounts:
            print("[ERROR] No customers/accounts found. Run seed_data.py first.")
            return

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        scenarios = [
            (500,   3000,  "deposit",    None,  None),
            (100,   2000,  "payment",    None,  None),
            (200,   5000,  "transfer",   None,  None),
            (9500,  9999,  "cash",       None,  None),
            (9600,  9900,  "cash",       None,  None),
            (15000, 40000, "wire",       "IR",  "US"),
            (1000,  1000,  "transfer",   None,  None),
            (5000,  5000,  "withdrawal", None,  None),
            (50,    100,   "transfer",   None,  None),
            (30,    80,    "payment",    None,  None),
            (20000, 60000, "wire",       "RU",  "DE"),
            (300,   2500,  "deposit",    None,  None),
        ]

        count = 0
        for i in range(20):
            customer = random.choice(customers)
            customer_accounts = [a for a in accounts if a.customer_id == customer.id]
            if not customer_accounts:
                continue

            from_acc = random.choice(customer_accounts)
            sc = random.choice(scenarios)
            amount = round(random.uniform(sc[0], sc[1]), 2) if sc[0] != sc[1] else float(sc[0])
            txn_type = sc[2]
            orig_country = sc[3] or customer.country
            dest_country = sc[4] or customer.country

            to_customer = random.choice([c for c in customers if c.id != customer.id])
            to_accounts = [a for a in accounts if a.customer_id == to_customer.id]
            to_acc = random.choice(to_accounts) if to_accounts else None

            created_at = today_start + timedelta(
                hours=random.randint(0, max(now.hour, 1)),
                minutes=random.randint(0, 59),
            )

            txn = Transaction(
                reference=f"TXN-{created_at.strftime('%Y%m%d%H%M%S')}-{random.randint(10000,99999)}",
                from_account_id=from_acc.id,
                to_account_id=to_acc.id if to_acc else None,
                from_customer_id=customer.id,
                to_customer_id=to_customer.id,
                amount=amount,
                currency=from_acc.currency,
                transaction_type=txn_type,
                originating_country=orig_country,
                destination_country=dest_country,
                is_international=(orig_country != dest_country),
                channel=random.choice(["online", "branch", "mobile", "atm"]),
                status="completed",
                description=f"Auto-generated transaction {i+1}",
            )
            txn.created_at = created_at
            db.add(txn)
            db.flush()

            try:
                matches = rules_engine.evaluate(txn, db)
                if matches:
                    alert_service.create_alerts_from_matches(matches, txn, db)
            except Exception:
                pass

            count += 1

        db.commit()
        print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Daily seed: {count} transactions added.")

    finally:
        db.close()


if __name__ == "__main__":
    seed_today()
