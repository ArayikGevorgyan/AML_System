from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
import dns.resolver

from database import get_db
from core.dependencies import get_current_user, require_admin
from models.user import User
from schemas.auth import (
    LoginRequest, TokenResponse, UserCreate, UserOut, UserUpdate,
    SendVerificationRequest,
)
from services.auth_service import auth_service
from services.audit_service import audit_service
from services.verification_service import verification_service
from services.email_service import email_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _check_email_domain(email: str) -> bool:
    try:
        domain = email.split('@')[1]
        dns.resolver.resolve(domain, 'MX')
        return True
    except Exception:
        return False


@router.post("/send-verification", status_code=200)
def send_verification(data: SendVerificationRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()

    if not _check_email_domain(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This email address does not exist. Please enter a valid email.",
        )

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email is already registered.",
        )

    code = verification_service.generate(email)
    email_service.send_verification_code(email, code)

    return {"message": "Verification code sent. Please check your inbox."}


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login(request, db)


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    email = data.email.strip().lower()

    if not data.verification_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email verification code is required.",
        )
    if not verification_service.verify(email, data.verification_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code.",
        )

    user = auth_service.create_user(data, db, created_by=None)
    verification_service.consume(email)
    return user


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    audit_service.log(db, action="LOGOUT", user=current_user)
    return {"message": "Logged out successfully"}


@router.get("/users", response_model=list[UserOut])
def list_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return auth_service.get_all_users(db)


@router.post("/users", response_model=UserOut)
def create_user(
    data: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    plain_password = data.password
    new_user = auth_service.create_user(data, db, created_by=current_user)
    email_service.send_welcome_credentials(
        to_email=new_user.email,
        full_name=new_user.full_name,
        username=new_user.username,
        password=plain_password,
        role=new_user.role,
    )
    return new_user


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return auth_service.update_user(user_id, data.model_dump(exclude_none=True), db, current_user)


@router.put("/profile", response_model=UserOut)
def update_profile(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    update_data = data.model_dump(exclude_none=True)
    update_data.pop("password", None)
    return auth_service.update_user(current_user.id, update_data, db, current_user)


@router.post("/send-password-reset")
def send_password_reset(
    data: SendVerificationRequest,
    current_user: User = Depends(get_current_user),
):
    code = verification_service.generate(current_user.email)
    email_service.send_verification_code(current_user.email, code)
    return {"message": "Verification code sent to your registered email."}


@router.put("/change-password")
def change_password(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from core.security import hash_password
    from services.auth_service import _validate_password
    code = data.get("verification_code", "")
    new_password = data.get("new_password", "")
    if not verification_service.verify(current_user.email, code):
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")
    _validate_password(new_password)
    current_user.password_hash = hash_password(new_password)
    db.commit()
    verification_service.consume(current_user.email)
    return {"message": "Password updated successfully."}
