"""
Seed Data Script
================
Populates the database with realistic demo data:
- 3 users (admin, analyst, supervisor)
- 8 AML rules
- 20 customers (varied risk levels, nationalities)
- 30 accounts
- 100+ transactions (including suspicious ones)
- Auto-generates alerts via the rules engine

Run from backend/: python scripts/seed_data.py
"""

import sys
import random
from pathlib import Path
from datetime import datetime, timedelta, timezone, date

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal, create_tables
from models.user import User
from models.customer import Customer
from models.account import Account
from models.transaction import Transaction
from models.rule import Rule
from core.security import hash_password
from services.rules_engine import rules_engine
from services.alert_service import alert_service

random.seed(42)


def seed_users(db) -> dict:
    print("[SEED] Creating users ...")
    users = {}
    user_data = [
        ("admin", "admin@amlsystem.io", "Admin User", "admin", "Admin@123"),
        ("ArayikAnalyst", "arayik.analyst@amlsystem.io", "Arayik Analyst", "analyst", "Analyst@123"),
        ("ArayikSupervisor", "arayik.supervisor@amlsystem.io", "Arayik Supervisor", "supervisor", "Super@123"),
        ("alee", "a.lee@amlsystem.io", "Alex Lee", "analyst", "Analyst@123"),
    ]
    for username, email, full_name, role, password in user_data:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            users[username] = existing
            continue
        u = User(
            username=username,
            email=email,
            full_name=full_name,
            role=role,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(u)
        db.flush()
        users[username] = u
    db.commit()
    print(f"[SEED] {len(users)} users ready.")
    return users


def seed_rules(db, admin_user) -> list:
    print("[SEED] Creating AML rules ...")
    if db.query(Rule).count() > 0:
        print("[SEED] Rules already exist, skipping.")
        return db.query(Rule).all()

    rules_data = [
        {
            "name": "Large Cash Transaction",
            "description": "Single transaction exceeds $10,000 reporting threshold",
            "category": "large_transaction",
            "threshold_amount": 10000.0,
            "severity": "high",
        },
        {
            "name": "Transaction Structuring (Smurfing)",
            "description": "Multiple transactions just below $10,000 to evade reporting",
            "category": "structuring",
            "threshold_amount": 10000.0,
            "time_window_hours": 72,
            "severity": "critical",
        },
        {
            "name": "High Transaction Frequency",
            "description": "More than 5 transactions within a 24-hour window",
            "category": "frequency",
            "threshold_count": 5,
            "time_window_hours": 24,
            "severity": "medium",
        },
        {
            "name": "High Velocity Movement",
            "description": "Cumulative outflow exceeds $25,000 in 24 hours",
            "category": "velocity",
            "threshold_amount": 25000.0,
            "time_window_hours": 24,
            "severity": "high",
        },
        {
            "name": "High-Risk Country Transaction",
            "description": "Transaction originates from or is destined to a sanctioned/high-risk country",
            "category": "high_risk_country",
            "severity": "critical",
        },
        {
            "name": "Rapid Fund Movement",
            "description": "Funds received and transferred out within 24 hours",
            "category": "rapid_movement",
            "threshold_amount": 5000.0,
            "time_window_hours": 24,
            "severity": "high",
        },
        {
            "name": "Suspicious Round Amount",
            "description": "Round-number transactions above $1,000 suggesting manual layering",
            "category": "round_amount",
            "threshold_amount": 1000.0,
            "time_window_hours": 48,
            "severity": "low",
        },
        {
            "name": "PEP Transaction Monitor",
            "description": "Any transaction involving a Politically Exposed Person",
            "category": "pep_transaction",
            "threshold_amount": 0.0,
            "severity": "high",
        },
        {
            "name": "Micro-Transaction Pattern",
            "description": "4+ transactions each ≤$100 within 1 hour with avg interval ≤30 min — indicates automated account testing or micro-layering",
            "category": "micro_transaction",
            "threshold_amount": 100.0,
            "threshold_count": 4,
            "time_window_hours": 1,
            "severity": "medium",
        },
    ]

    created = []
    for rd in rules_data:
        rule = Rule(
            name=rd["name"],
            description=rd.get("description"),
            category=rd["category"],
            threshold_amount=rd.get("threshold_amount"),
            threshold_count=rd.get("threshold_count"),
            time_window_hours=rd.get("time_window_hours"),
            severity=rd["severity"],
            is_active=True,
            created_by=admin_user.id,
        )
        db.add(rule)
        created.append(rule)
    db.commit()
    print(f"[SEED] {len(created)} rules created.")
    return created


def seed_customers(db, admin_user) -> list:
    print("[SEED] Creating customers ...")
    if db.query(Customer).count() > 0:
        print("[SEED] Customers already exist, skipping.")
        return db.query(Customer).all()

    customers_data = [
        ("Ahmed Al-Rashid", "ahmed.rashid@email.com", "IQ", "high", True, False, "Businessman", 120000),
        ("Maria Garcia", "m.garcia@email.com", "MX", "medium", False, False, "Accountant", 85000),
        ("Chen Wei", "chen.wei@email.com", "CN", "low", False, False, "Engineer", 75000),
        ("Fatima Al-Zahra", "f.alzahra@email.com", "IR", "critical", False, True, "Unknown", 0),
        ("Robert Johnson", "r.johnson@email.com", "US", "low", False, False, "Teacher", 60000),
        ("Olga Petrov", "o.petrov@email.com", "RU", "high", True, False, "Politician", 200000),
        ("James Kim", "j.kim@email.com", "KR", "low", False, False, "Developer", 95000),
        ("Hassan Ibrahim", "h.ibrahim@email.com", "SD", "critical", False, True, "Unknown", 0),
        ("Sofia Rossi", "s.rossi@email.com", "IT", "low", False, False, "Doctor", 110000),
        ("Mohammad Khaled", "m.khaled@email.com", "SY", "high", False, False, "Trader", 50000),
        ("Anna Müller", "a.muller@email.com", "DE", "low", False, False, "Architect", 90000),
        ("Carlos Rivera", "c.rivera@email.com", "CO", "medium", False, False, "Entrepreneur", 150000),
        ("Yuki Tanaka", "y.tanaka@email.com", "JP", "low", False, False, "Manager", 88000),
        ("Ibrahim Al-Sayed", "i.alsayed@email.com", "KP", "critical", False, True, "Unknown", 0),
        ("Elena Volkov", "e.volkov@email.com", "BY", "high", True, False, "Official", 180000),
        ("David Cohen", "d.cohen@email.com", "IL", "low", False, False, "Lawyer", 130000),
        ("Amina Diallo", "a.diallo@email.com", "NG", "medium", False, False, "Nurse", 45000),
        ("Viktor Kozlov", "v.kozlov@email.com", "RU", "high", False, False, "Investor", 500000),
        ("Sara Al-Amiri", "s.alamiri@email.com", "AE", "medium", False, False, "Consultant", 140000),
        ("Pedro Santos", "p.santos@email.com", "BR", "low", False, False, "Salesman", 55000),
    ]

    created = []
    for i, (name, email, country, risk, pep, flag, occ, income) in enumerate(customers_data):
        c = Customer(
            customer_number=f"CUS-{i+1:06d}",
            full_name=name,
            email=email,
            phone=f"+1-555-{random.randint(1000,9999)}-{random.randint(1000,9999)}",
            nationality=country,
            country=country,
            risk_level=risk,
            pep_status=pep,
            sanctions_flag=flag,
            occupation=occ,
            annual_income=float(income),
            source_of_funds="employment" if income > 0 else "unknown",
            created_by=admin_user.id,
            date_of_birth=date(random.randint(1960, 1995), random.randint(1, 12), random.randint(1, 28)),
        )
        db.add(c)
        db.flush()
        created.append(c)
    db.commit()
    print(f"[SEED] {len(created)} customers created.")
    return created


def seed_accounts(db, customers: list) -> list:
    print("[SEED] Creating accounts ...")
    if db.query(Account).count() > 0:
        print("[SEED] Accounts already exist, skipping.")
        return db.query(Account).all()

    account_types = ["checking", "savings", "business", "investment"]
    currencies = ["USD", "EUR", "GBP", "USD", "USD"]
    created = []
    for i, customer in enumerate(customers):
        n_accounts = random.choice([1, 1, 2, 2, 3])
        for j in range(n_accounts):
            acc = Account(
                account_number=f"ACC-{(i*3+j+1):010d}",
                customer_id=customer.id,
                account_type=random.choice(account_types),
                currency=random.choice(currencies),
                balance=round(random.uniform(500, 250000), 2),
                status="active",
                opened_date=date(random.randint(2015, 2023), random.randint(1, 12), 1),
                country=customer.country,
            )
            db.add(acc)
            db.flush()
            created.append(acc)
    db.commit()
    print(f"[SEED] {len(created)} accounts created.")
    return created


def seed_transactions(db, customers: list, accounts: list):
    print("[SEED] Creating transactions ...")
    if db.query(Transaction).count() > 0:
        print("[SEED] Transactions already exist, skipping.")
        return

    txn_types = ["transfer", "deposit", "withdrawal", "wire", "payment", "cash"]
    high_risk_countries = ["IR", "KP", "SY", "SD", "RU", "BY", "CU"]

    # Normal transactions
    normal_scenarios = [
        (500, 3000, "deposit", None, None),
        (100, 2000, "payment", None, None),
        (50, 1500, "transfer", None, None),
        (200, 5000, "withdrawal", None, None),
    ]

    # Suspicious scenarios
    suspicious_scenarios = [
        (10001, 50000, "wire", "IR", "US"),        # Large + high risk country
        (9500, 9999, "cash", None, None),           # Structuring
        (9600, 9800, "cash", None, None),           # Structuring
        (9700, 9950, "transfer", None, None),       # Structuring
        (50000, 100000, "wire", "RU", "US"),        # Very large + Russia
        (15000, 30000, "wire", "KP", "CN"),         # North Korea
        (1000, 1000, "transfer", None, None),       # Round amount
        (5000, 5000, "cash", None, None),           # Round amount
        (10000, 10000, "withdrawal", None, None),   # Exact threshold
    ]

    count = 0
    base_time = datetime.now(timezone.utc) - timedelta(days=30)

    for i in range(120):
        customer = random.choice(customers)
        customer_accounts = [a for a in accounts if a.customer_id == customer.id]
        if not customer_accounts:
            continue

        from_acc = random.choice(customer_accounts)

        # Pick scenario
        is_suspicious = i < 35 or customer.risk_level in ("high", "critical")
        if is_suspicious and suspicious_scenarios:
            sc = random.choice(suspicious_scenarios)
            amount = round(random.uniform(sc[0], sc[1]), 2) if sc[0] != sc[1] else sc[0]
            txn_type = sc[2]
            orig_country = sc[3] or customer.country
            dest_country = sc[4] or random.choice(["US", "UK", "DE", "FR"])
        else:
            sc = random.choice(normal_scenarios)
            amount = round(random.uniform(sc[0], sc[1]), 2)
            txn_type = sc[2]
            orig_country = customer.country
            dest_country = customer.country

        to_customer = random.choice([c for c in customers if c.id != customer.id])
        to_accounts = [a for a in accounts if a.customer_id == to_customer.id]
        to_acc = random.choice(to_accounts) if to_accounts else None

        # Randomize timestamp within last 30 days
        created_at = base_time + timedelta(
            days=random.randint(0, 29),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )

        txn = Transaction(
            reference=f"TXN-{created_at.strftime('%Y%m%d')}-{i+1:06d}",
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
            description=f"Transaction {i+1}",
        )
        # Manually set created_at for demo
        txn.created_at = created_at
        db.add(txn)
        db.flush()

        # Run rules engine
        try:
            matches = rules_engine.evaluate(txn, db)
            if matches:
                alert_service.create_alerts_from_matches(matches, txn, db)
        except Exception as e:
            pass  # Don't fail seed on rule errors

        count += 1

    db.commit()
    print(f"[SEED] {count} transactions created.")


def seed_cases(db, users: dict):
    """Create a few sample cases from existing alerts."""
    from models.alert import Alert
    from models.case import Case, CaseNote

    if db.query(Case).count() > 0:
        return

    analyst = users.get("jsmith")
    supervisor = users.get("mwilson")
    if not analyst:
        return

    open_alerts = db.query(Alert).filter(Alert.status == "open").limit(5).all()
    statuses = ["open", "investigating", "pending_review", "escalated", "closed"]

    for i, alert in enumerate(open_alerts):
        case = Case(
            case_number=f"CASE-{datetime.now().year}-{i+1:05d}",
            alert_id=alert.id,
            title=f"Investigation: {alert.reason[:50]}",
            description=f"Opened from alert {alert.alert_number}",
            status=statuses[i % len(statuses)],
            priority=alert.severity,
            assigned_to=analyst.id,
            created_by=supervisor.id if supervisor else analyst.id,
        )
        db.add(case)
        db.flush()

        note = CaseNote(
            case_id=case.id,
            user_id=analyst.id,
            note="Initial review started. Gathering transaction history.",
            note_type="comment",
        )
        db.add(note)

        if i == 2:
            alert.status = "under_review"

    db.commit()
    print("[SEED] Sample cases created.")


def run():
    print("=" * 60)
    print("  AML System — Database Seeding")
    print("=" * 60)
    create_tables()
    db = SessionLocal()
    try:
        users = seed_users(db)
        rules = seed_rules(db, users["admin"])
        customers = seed_customers(db, users["admin"])
        accounts = seed_accounts(db, customers)
        seed_transactions(db, customers, accounts)
        seed_cases(db, users)
        print("=" * 60)
        print("[SEED] All done!")
        print("\n  Login credentials:")
        print("  admin    / Admin@123   (role: admin)")
        print("  jsmith   / Analyst@123 (role: analyst)")
        print("  mwilson  / Super@123   (role: supervisor)")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    run()
