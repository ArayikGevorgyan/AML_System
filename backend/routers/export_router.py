import csv
import io
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
from core.dependencies import get_current_user
from models.user import User
from models.alert import Alert
from models.case import Case
from models.transaction import Transaction

router = APIRouter(prefix="/export", tags=["Export"])

def make_csv(headers, rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=export.csv"}
    )

@router.get("/alerts.csv")
def export_alerts(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    alerts = db.query(Alert).order_by(Alert.created_at.desc()).limit(1000).all()
    headers = ["Alert Number", "Severity", "Status", "Risk Score", "Reason", "Created At"]
    rows = [[a.alert_number, a.severity, a.status, a.risk_score, a.reason, str(a.created_at)] for a in alerts]
    return make_csv(headers, rows)

@router.get("/transactions.csv")
def export_transactions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    txns = db.query(Transaction).order_by(Transaction.created_at.desc()).limit(1000).all()
    headers = ["Ref", "Amount", "Currency", "Type", "From Country", "To Country", "Risk Score", "Flagged", "Created At"]
    rows = [[t.reference, t.amount, t.currency, t.transaction_type, t.originating_country, t.destination_country, t.risk_score, t.flagged, str(t.created_at)] for t in txns]
    return make_csv(headers, rows)

@router.get("/cases.csv")
def export_cases(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cases = db.query(Case).order_by(Case.created_at.desc()).limit(1000).all()
    headers = ["Case Number", "Status", "SAR Filed", "SAR Reference", "Created At"]
    rows = [[c.case_number, c.status, c.sar_filed, c.sar_reference, str(c.created_at)] for c in cases]
    return make_csv(headers, rows)
