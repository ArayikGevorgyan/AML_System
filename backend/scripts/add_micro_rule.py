"""
Adds the Micro-Transaction Pattern rule to an existing database.
Run from backend/: python scripts/add_micro_rule.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal, create_tables
from models.rule import Rule
from models.user import User

create_tables()
db = SessionLocal()

# Check if rule already exists
existing = db.query(Rule).filter(Rule.category == "micro_transaction").first()
if existing:
    print("[INFO] Micro-transaction rule already exists. Nothing to do.")
    db.close()
    sys.exit(0)

admin = db.query(User).filter(User.role == "admin").first()
if not admin:
    print("[ERROR] No admin user found. Run seed_data.py first.")
    db.close()
    sys.exit(1)

rule = Rule(
    name="Micro-Transaction Pattern",
    description="4+ transactions each ≤$100 within 1 hour with avg interval ≤30 min — indicates automated account testing or micro-layering",
    category="micro_transaction",
    threshold_amount=100.0,
    threshold_count=4,
    time_window_hours=1,
    severity="medium",
    is_active=True,
    created_by=admin.id,
)
db.add(rule)
db.commit()
print(f"[OK] Micro-Transaction Pattern rule added (id={rule.id}).")
db.close()
