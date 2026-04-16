from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from core.dependencies import get_current_user
from models.customer import Customer
from services.risk_scoring_service import compute_customer_risk_score, compute_all_customer_scores
from services.predictive_risk_service import predict_customer_risk

router = APIRouter(prefix="/risk-scoring", tags=["Risk Scoring"])


@router.get("/customers")
def all_customer_scores(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Compute and return risk scores for all customers, sorted highest first."""
    return compute_all_customer_scores(db)


@router.get("/customers/{customer_id}")
def customer_score(customer_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Compute risk score for a single customer."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Customer not found")
    return compute_customer_risk_score(customer, db)


@router.get("/customers/{customer_id}/predict")
def predict_risk(customer_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Predict future risk trajectory for a customer based on behavioral trends."""
    return predict_customer_risk(customer_id, db)
