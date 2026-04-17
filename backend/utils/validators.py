"""
AML Input Validators
======================
Validation functions for API inputs, user-supplied parameters, and
data entry fields. All functions raise ValueError with descriptive
messages on invalid input.

Usage:
    from utils.validators import validate_date_range, validate_amount

    try:
        validate_date_range(start, end, max_days=365)
        validate_amount(request.amount, min_val=0.01, max_val=1_000_000)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
"""

import re
from datetime import datetime, date
from typing import Optional


# ---------------------------------------------------------------------------
# Date range validation
# ---------------------------------------------------------------------------

def validate_date_range(
    start: datetime,
    end: datetime,
    max_days: int = 365,
) -> None:
    """
    Validate that a date range is logically consistent and within limits.

    Args:
        start:    Start datetime (inclusive).
        end:      End datetime (inclusive).
        max_days: Maximum allowed range in days (default 365).

    Raises:
        ValueError: If start > end, or range exceeds max_days.
    """
    if start is None or end is None:
        raise ValueError("Both start and end dates are required.")

    if end < start:
        raise ValueError(
            f"End date ({end.date()}) cannot be before start date ({start.date()})."
        )

    delta = (end - start).days
    if delta > max_days:
        raise ValueError(
            f"Date range of {delta} days exceeds the maximum of {max_days} days."
        )


# ---------------------------------------------------------------------------
# Amount validation
# ---------------------------------------------------------------------------

def validate_amount(
    value: float,
    min_val: float = 0.01,
    max_val: float = 100_000_000.0,
    field_name: str = "amount",
) -> None:
    """
    Validate that a monetary amount is within acceptable bounds.

    Args:
        value:      The amount to validate.
        min_val:    Minimum allowed value (default $0.01).
        max_val:    Maximum allowed value (default $100M).
        field_name: Field name for error messages.

    Raises:
        ValueError: If value is outside [min_val, max_val].
    """
    if value is None:
        raise ValueError(f"{field_name} is required.")

    if not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number, got {type(value).__name__}.")

    if value < min_val:
        raise ValueError(
            f"{field_name} ({value:,.2f}) is below the minimum allowed value ({min_val:,.2f})."
        )

    if value > max_val:
        raise ValueError(
            f"{field_name} ({value:,.2f}) exceeds the maximum allowed value ({max_val:,.2f})."
        )


# ---------------------------------------------------------------------------
# Name validation
# ---------------------------------------------------------------------------

def validate_name(name: str, field_name: str = "name", max_len: int = 200) -> None:
    """
    Validate a person or entity name.

    Rules:
      - Must not be empty or whitespace-only
      - Must be at most max_len characters
      - Must not consist entirely of special characters

    Args:
        name:       The name string to validate.
        field_name: Field name for error messages.
        max_len:    Maximum length (default 200).

    Raises:
        ValueError: If the name fails validation.
    """
    if not name or not name.strip():
        raise ValueError(f"{field_name} cannot be empty.")

    name = name.strip()

    if len(name) > max_len:
        raise ValueError(
            f"{field_name} is too long ({len(name)} chars). Maximum is {max_len}."
        )

    if len(name) < 2:
        raise ValueError(f"{field_name} must be at least 2 characters long.")

    # Reject strings that are only symbols
    if re.fullmatch(r"[^a-zA-Z\u00C0-\u024F\u0400-\u04FF]+", name):
        raise ValueError(f"{field_name} must contain at least one letter.")


# ---------------------------------------------------------------------------
# Country code validation
# ---------------------------------------------------------------------------

VALID_ISO2_PATTERN = re.compile(r"^[A-Z]{2}$")

def validate_country_code(code: str, field_name: str = "country") -> None:
    """
    Validate a two-letter ISO 3166-1 alpha-2 country code.

    Args:
        code:       The country code string (e.g. "US", "DE").
        field_name: Field name for error messages.

    Raises:
        ValueError: If code is not a 2-letter uppercase string.
    """
    if not code:
        raise ValueError(f"{field_name} is required.")

    code = code.strip().upper()

    if not VALID_ISO2_PATTERN.match(code):
        raise ValueError(
            f"{field_name} '{code}' is not a valid ISO 3166-1 alpha-2 country code "
            f"(expected 2 uppercase letters, e.g. 'US', 'GB')."
        )


# ---------------------------------------------------------------------------
# Risk level validation
# ---------------------------------------------------------------------------

VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}

def validate_risk_level(level: str, field_name: str = "risk_level") -> None:
    """
    Validate that a risk level string is one of the accepted values.

    Args:
        level:      The risk level string.
        field_name: Field name for error messages.

    Raises:
        ValueError: If level is not in VALID_RISK_LEVELS.
    """
    if not level:
        raise ValueError(f"{field_name} is required.")

    if level.lower() not in VALID_RISK_LEVELS:
        raise ValueError(
            f"Invalid {field_name} '{level}'. "
            f"Must be one of: {sorted(VALID_RISK_LEVELS)}."
        )


# ---------------------------------------------------------------------------
# Pagination validation
# ---------------------------------------------------------------------------

def validate_pagination(
    skip: int,
    limit: int,
    max_limit: int = 500,
) -> None:
    """
    Validate pagination parameters (skip / limit).

    Args:
        skip:      Number of records to skip (must be >= 0).
        limit:     Number of records to return.
        max_limit: Maximum allowed limit (default 500).

    Raises:
        ValueError: If skip < 0 or limit is outside [1, max_limit].
    """
    if skip is None:
        skip = 0

    if skip < 0:
        raise ValueError(f"skip must be >= 0, got {skip}.")

    if limit is None or limit < 1:
        raise ValueError(f"limit must be >= 1, got {limit}.")

    if limit > max_limit:
        raise ValueError(
            f"limit ({limit}) exceeds the maximum of {max_limit}."
        )


# ---------------------------------------------------------------------------
# Email validation
# ---------------------------------------------------------------------------

EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

def validate_email(email: str) -> None:
    """
    Validate an email address format.

    Args:
        email: The email string to validate.

    Raises:
        ValueError: If the email format is invalid.
    """
    if not email or not email.strip():
        raise ValueError("Email address cannot be empty.")

    email = email.strip()

    if len(email) > 254:  # RFC 5321 max
        raise ValueError(f"Email address is too long (max 254 characters).")

    if not EMAIL_PATTERN.match(email):
        raise ValueError(
            f"'{email}' is not a valid email address format."
        )


# ---------------------------------------------------------------------------
# Transaction type validation
# ---------------------------------------------------------------------------

VALID_TRANSACTION_TYPES = {"transfer", "deposit", "withdrawal", "wire", "payment", "cash"}

def validate_transaction_type(type_str: str) -> None:
    """
    Validate a transaction type string.

    Args:
        type_str: The transaction type string.

    Raises:
        ValueError: If the type is not in the allowed set.
    """
    if not type_str:
        raise ValueError("transaction_type is required.")

    if type_str.lower() not in VALID_TRANSACTION_TYPES:
        raise ValueError(
            f"Invalid transaction_type '{type_str}'. "
            f"Must be one of: {sorted(VALID_TRANSACTION_TYPES)}."
        )


# ---------------------------------------------------------------------------
# String sanitization
# ---------------------------------------------------------------------------

def sanitize_string(
    s: str,
    max_len: int = 500,
    strip_html: bool = True,
) -> str:
    """
    Sanitize a user-supplied string: strip whitespace, truncate, remove HTML tags.

    Args:
        s:          Input string.
        max_len:    Maximum length after sanitization (default 500).
        strip_html: If True, remove any HTML-like tags.

    Returns:
        Sanitized string.

    Raises:
        ValueError: If the resulting string is empty after sanitization.
    """
    if not s:
        return ""

    s = s.strip()

    if strip_html:
        s = re.sub(r"<[^>]+>", "", s)

    # Collapse multiple whitespace
    s = re.sub(r"\s+", " ", s)

    if len(s) > max_len:
        s = s[:max_len]

    return s
