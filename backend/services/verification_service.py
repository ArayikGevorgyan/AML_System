import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple, Optional


class VerificationService:
    """
    Stores short-lived 6-digit verification codes in memory.
    In production this would be backed by Redis.
    """

    CODE_TTL_MINUTES = 10

    def __init__(self):
        # { email: (code, expires_at) }
        self._store: Dict[str, Tuple[str, datetime]] = {}

    def generate(self, email: str) -> str:
        """Generate a new 6-digit code for the given email and store it."""
        code = ''.join(secrets.choice(string.digits) for _ in range(6))
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.CODE_TTL_MINUTES)
        self._store[email.lower()] = (code, expires_at)
        return code

    def verify(self, email: str, code: str) -> bool:
        """Return True if the code matches and has not expired."""
        entry = self._store.get(email.lower())
        if not entry:
            return False
        stored_code, expires_at = entry
        if datetime.now(timezone.utc) > expires_at:
            del self._store[email.lower()]
            return False
        return stored_code == code

    def consume(self, email: str):
        """Remove the code after successful verification."""
        self._store.pop(email.lower(), None)

    def has_pending(self, email: str) -> bool:
        """Return True if a non-expired code exists for this email."""
        entry = self._store.get(email.lower())
        if not entry:
            return False
        _, expires_at = entry
        if datetime.now(timezone.utc) > expires_at:
            del self._store[email.lower()]
            return False
        return True


verification_service = VerificationService()
