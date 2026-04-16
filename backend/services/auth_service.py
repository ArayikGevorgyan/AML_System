import re
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from models.user import User
from schemas.auth import UserCreate, LoginRequest, TokenResponse, UserOut
from core.security import hash_password, verify_password, create_access_token
from services.audit_service import audit_service


def _validate_password(password: str):
    errors = []
    if len(password) < 8:
        errors.append("at least 8 characters")
    if not re.search(r"[A-Z]", password):
        errors.append("one uppercase letter")
    if not re.search(r"[0-9]", password):
        errors.append("one number")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("one special character (!@#$%^&* etc.)")
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Password must contain: {', '.join(errors)}.",
        )


class AuthService:

    def login(self, request: LoginRequest, db: Session) -> TokenResponse:
        user = db.query(User).filter(User.username == request.username).first()
        if not user or not verify_password(request.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
            )
        user.last_login = datetime.now(timezone.utc)
        db.commit()

        token = create_access_token({"sub": str(user.id), "role": user.role})
        audit_service.log(db, action="LOGIN", user=user, description="User logged in")
        return TokenResponse(access_token=token, user=UserOut.model_validate(user))

    def create_user(self, data: UserCreate, db: Session, created_by: Optional[User] = None) -> User:
        _validate_password(data.password)
        if db.query(User).filter(User.username == data.username).first():
            raise HTTPException(status_code=400, detail="Username already taken")
        if db.query(User).filter(User.email == data.email).first():
            raise HTTPException(status_code=400, detail="Email already in use")

        user = User(
            username=data.username,
            email=data.email,
            full_name=data.full_name,
            password_hash=hash_password(data.password),
            role=data.role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        audit_service.log(
            db, action="CREATE_USER", user=created_by,
            entity_type="user", entity_id=user.id,
            new_value={"username": user.username, "role": user.role},
        )
        return user

    def get_all_users(self, db: Session):
        return db.query(User).all()

    def update_user(self, user_id: int, data: dict, db: Session, current_user: User) -> User:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        for key, val in data.items():
            if val is not None and hasattr(user, key):
                setattr(user, key, val)
        db.commit()
        db.refresh(user)
        audit_service.log(db, action="UPDATE_USER", user=current_user,
                          entity_type="user", entity_id=user_id)
        return user


auth_service = AuthService()
