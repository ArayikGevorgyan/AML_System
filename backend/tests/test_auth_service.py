"""
Tests for Auth Service
=======================
Tests password validation, login logic, and user creation.

Run with:
    pytest backend/tests/test_auth_service.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from services.auth_service import AuthService, _validate_password


@pytest.fixture
def service():
    return AuthService()


# ── Password Validation ────────────────────────────────────────────────────

class TestValidatePassword:
    def test_valid_password_passes(self):
        _validate_password("SecurePass1!")  # Should not raise

    def test_too_short_raises(self):
        with pytest.raises(HTTPException) as exc:
            _validate_password("Ab1!")
        assert "8 characters" in exc.value.detail

    def test_no_uppercase_raises(self):
        with pytest.raises(HTTPException) as exc:
            _validate_password("securepass1!")
        assert "uppercase" in exc.value.detail

    def test_no_number_raises(self):
        with pytest.raises(HTTPException) as exc:
            _validate_password("SecurePass!")
        assert "one number" in exc.value.detail

    def test_no_special_char_raises(self):
        with pytest.raises(HTTPException) as exc:
            _validate_password("SecurePass1")
        assert "special" in exc.value.detail

    def test_multiple_violations_in_message(self):
        with pytest.raises(HTTPException) as exc:
            _validate_password("abc")
        detail = exc.value.detail
        # Multiple requirements should be listed
        assert "8 characters" in detail

    def test_exactly_8_chars_valid(self):
        _validate_password("Secure1!")  # Should not raise

    @pytest.mark.parametrize("password", [
        "MyPassword1@",
        "ComplexP@ss9",
        "Hello_World1",
        "Test#2024pass",
    ])
    def test_valid_passwords(self, password):
        _validate_password(password)  # Should not raise


# ── Login ──────────────────────────────────────────────────────────────────

class TestLogin:
    def _make_user(self, active=True):
        user = MagicMock()
        user.id = 1
        user.username = "testuser"
        user.role = "analyst"
        user.is_active = active
        user.last_login = None
        return user

    def test_wrong_username_raises_401(self, service):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        request = MagicMock(username="wrong", password="Test123!")

        with pytest.raises(HTTPException) as exc:
            service.login(request, db)
        assert exc.value.status_code == 401

    def test_wrong_password_raises_401(self, service):
        user = self._make_user()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        request = MagicMock(username="testuser", password="WrongPass1!")

        with patch("services.auth_service.verify_password", return_value=False):
            with pytest.raises(HTTPException) as exc:
                service.login(request, db)
            assert exc.value.status_code == 401

    def test_inactive_user_raises_403(self, service):
        user = self._make_user(active=False)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        request = MagicMock(username="testuser", password="Test123!")

        with patch("services.auth_service.verify_password", return_value=True):
            with pytest.raises(HTTPException) as exc:
                service.login(request, db)
            assert exc.value.status_code == 403

    def test_successful_login_returns_token(self, service):
        user = self._make_user()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        request = MagicMock(username="testuser", password="Test123!")

        with patch("services.auth_service.verify_password", return_value=True), \
             patch("services.auth_service.create_access_token", return_value="mock_token"), \
             patch("services.auth_service.audit_service") as mock_audit, \
             patch("services.auth_service.UserOut.model_validate") as mock_validate:
            mock_validate.return_value = MagicMock()
            result = service.login(request, db)
            assert result.access_token == "mock_token"


# ── Create User ────────────────────────────────────────────────────────────

class TestCreateUser:
    def test_duplicate_username_raises_400(self, service):
        existing_user = MagicMock()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = existing_user
        data = MagicMock(username="taken", email="new@test.com", password="Test123!")

        with pytest.raises(HTTPException) as exc:
            service.create_user(data, db)
        assert exc.value.status_code == 400
        assert "Username" in exc.value.detail

    def test_weak_password_raises_422(self, service):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        data = MagicMock(username="newuser", email="new@test.com", password="weak")

        with pytest.raises(HTTPException) as exc:
            service.create_user(data, db)
        assert exc.value.status_code == 422
