"""
AML Output Formatters
=======================
Formatting functions for displaying AML data in reports, API responses,
and CLI output. Functions produce human-readable string representations
without modifying underlying data.

Usage:
    from utils.formatters import format_currency, format_risk_level

    print(format_currency(12500.50, "USD"))   # "$12,500.50"
    print(format_risk_level("high"))           # "HIGH ●"
    print(format_duration(5430))               # "1h 30m"
"""

from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# format_currency
# ---------------------------------------------------------------------------

CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CHF": "Fr",
    "CAD": "CA$",
    "AUD": "A$",
    "CNY": "¥",
    "HKD": "HK$",
    "SGD": "S$",
    "RUB": "₽",
    "INR": "₹",
    "KRW": "₩",
    "MXN": "Mex$",
    "BRL": "R$",
}


def format_currency(
    amount: float,
    currency: str = "USD",
    locale: str = "en_US",
    show_symbol: bool = True,
) -> str:
    """
    Format a monetary amount with currency symbol and thousand separators.

    Args:
        amount:      Numeric amount.
        currency:    ISO 4217 currency code (default "USD").
        locale:      Locale string (used for separator style, default en_US).
        show_symbol: If True, prefix with currency symbol.

    Returns:
        Formatted currency string (e.g. "$12,500.50").
    """
    if amount is None:
        return "N/A"

    # Japanese yen has no decimal places
    decimals = 0 if currency == "JPY" else 2

    if locale == "en_US":
        formatted = f"{abs(amount):,.{decimals}f}"
    else:
        # European style: period as thousands sep, comma as decimal
        int_part = int(abs(amount))
        dec_part = abs(amount) - int_part
        int_str = f"{int_part:,}".replace(",", ".")
        if decimals > 0:
            formatted = f"{int_str},{dec_part:.{decimals}f}"[2:]  # strip "0."
            formatted = f"{int_str},{dec_part*100:02.0f}"
        else:
            formatted = int_str

    prefix = ""
    if show_symbol:
        symbol = CURRENCY_SYMBOLS.get(currency.upper(), currency)
        prefix = symbol

    sign = "-" if amount < 0 else ""
    return f"{sign}{prefix}{formatted}"


# ---------------------------------------------------------------------------
# format_risk_level
# ---------------------------------------------------------------------------

RISK_LEVEL_LABELS = {
    "low": "LOW",
    "medium": "MEDIUM",
    "high": "HIGH",
    "critical": "CRITICAL",
}

RISK_LEVEL_INDICATORS = {
    "low": "●",
    "medium": "●●",
    "high": "●●●",
    "critical": "●●●●",
}


def format_risk_level(level: str, include_indicator: bool = True) -> str:
    """
    Format a risk level string as a human-readable label with indicator dots.

    Args:
        level:             Risk level string ("low", "medium", "high", "critical").
        include_indicator: If True, append dot indicators.

    Returns:
        Formatted string (e.g. "HIGH ●●●").
    """
    level = (level or "unknown").lower()
    label = RISK_LEVEL_LABELS.get(level, level.upper())
    if include_indicator:
        indicator = RISK_LEVEL_INDICATORS.get(level, "")
        return f"{label} {indicator}".strip() if indicator else label
    return label


# ---------------------------------------------------------------------------
# format_alert_severity
# ---------------------------------------------------------------------------

SEVERITY_LABELS = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
}

SEVERITY_SYMBOLS = {
    "critical": "!!!",
    "high": "!!",
    "medium": "!",
    "low": "i",
}


def format_alert_severity(sev: str) -> str:
    """
    Format an alert severity string with a textual symbol prefix.

    Args:
        sev: Severity string ("critical", "high", "medium", "low").

    Returns:
        Formatted string (e.g. "[!!!] CRITICAL", "[i] LOW").
    """
    sev = (sev or "unknown").lower()
    label = SEVERITY_LABELS.get(sev, sev.upper())
    symbol = SEVERITY_SYMBOLS.get(sev, "?")
    return f"[{symbol}] {label}"


# ---------------------------------------------------------------------------
# format_date
# ---------------------------------------------------------------------------

DATE_FORMATS = {
    "iso": "%Y-%m-%dT%H:%M:%S",
    "short": "%Y-%m-%d",
    "long": "%B %d, %Y at %H:%M",
    "us": "%m/%d/%Y %H:%M",
    "report": "%d-%b-%Y",
}


def format_date(
    dt: Optional[datetime],
    fmt: str = "short",
    tz_label: bool = False,
) -> str:
    """
    Format a datetime object using a named format or a strftime pattern.

    Args:
        dt:       The datetime to format. If None, returns "N/A".
        fmt:      Format name (iso/short/long/us/report) or strftime pattern.
        tz_label: If True and dt is UTC-aware, append " UTC".

    Returns:
        Formatted date string.
    """
    if dt is None:
        return "N/A"

    pattern = DATE_FORMATS.get(fmt, fmt)
    formatted = dt.strftime(pattern)

    if tz_label and hasattr(dt, "tzinfo") and dt.tzinfo is not None:
        formatted += " UTC"

    return formatted


# ---------------------------------------------------------------------------
# format_duration
# ---------------------------------------------------------------------------

def format_duration(seconds: float) -> str:
    """
    Format a duration in seconds to a human-readable string.

    Examples:
        45       → "45s"
        3660     → "1h 1m"
        90000    → "1d 1h"
        86400*3  → "3d"

    Args:
        seconds: Duration in seconds (may be float).

    Returns:
        Human-readable duration string.
    """
    if seconds is None or seconds < 0:
        return "N/A"

    seconds = int(seconds)

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 and days == 0:
        parts.append(f"{minutes}m")
    if secs > 0 and days == 0 and hours == 0:
        parts.append(f"{secs}s")

    return " ".join(parts) if parts else "0s"


# ---------------------------------------------------------------------------
# format_percentage
# ---------------------------------------------------------------------------

def format_percentage(
    value: float,
    decimals: int = 1,
    include_sign: bool = False,
) -> str:
    """
    Format a float as a percentage string.

    Args:
        value:        The percentage value (e.g. 0.75 or 75.0).
        decimals:     Number of decimal places.
        include_sign: If True, prefix with + for positive values.

    Returns:
        Formatted percentage string (e.g. "75.0%", "+12.5%").
    """
    if value is None:
        return "N/A"

    # Auto-detect if value is in 0-1 range or 0-100 range
    if abs(value) <= 1.0 and abs(value) != 0:
        value = value * 100.0

    sign = "+" if include_sign and value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"


# ---------------------------------------------------------------------------
# format_large_number
# ---------------------------------------------------------------------------

def format_large_number(n: float, precision: int = 1) -> str:
    """
    Format a large number with K/M/B suffix for compact display.

    Examples:
        1200         → "1.2K"
        1_500_000    → "1.5M"
        2_100_000_000 → "2.1B"

    Args:
        n:         The number to format.
        precision: Decimal places in the output.

    Returns:
        Compact string with suffix.
    """
    if n is None:
        return "N/A"

    abs_n = abs(n)
    sign = "-" if n < 0 else ""

    if abs_n >= 1_000_000_000:
        return f"{sign}{abs_n / 1_000_000_000:.{precision}f}B"
    elif abs_n >= 1_000_000:
        return f"{sign}{abs_n / 1_000_000:.{precision}f}M"
    elif abs_n >= 1_000:
        return f"{sign}{abs_n / 1_000:.{precision}f}K"
    else:
        return f"{sign}{abs_n:.{precision}f}"


# ---------------------------------------------------------------------------
# truncate_string
# ---------------------------------------------------------------------------

def truncate_string(
    s: str,
    max_len: int = 100,
    suffix: str = "...",
) -> str:
    """
    Truncate a string to max_len characters, appending a suffix if truncated.

    Args:
        s:       Input string.
        max_len: Maximum output length including suffix.
        suffix:  String to append when truncated (default "...").

    Returns:
        Original string if within max_len, else truncated string with suffix.
    """
    if not s:
        return ""

    if len(s) <= max_len:
        return s

    cut = max_len - len(suffix)
    return s[:cut] + suffix


# ---------------------------------------------------------------------------
# format_customer_name
# ---------------------------------------------------------------------------

def format_customer_name(
    first: str,
    last: str,
    middle: Optional[str] = None,
    style: str = "full",
) -> str:
    """
    Format a customer's name from component parts.

    Styles:
      - "full":   "First [Middle] Last"
      - "formal": "Last, First [Middle]"
      - "abbrev": "First L."

    Args:
        first:  First name.
        last:   Last name.
        middle: Optional middle name.
        style:  One of "full", "formal", "abbrev".

    Returns:
        Formatted full name string.
    """
    first = (first or "").strip()
    last = (last or "").strip()
    middle = (middle or "").strip()

    if style == "formal":
        if middle:
            return f"{last}, {first} {middle[0]}."
        return f"{last}, {first}"
    elif style == "abbrev":
        last_initial = f" {last[0]}." if last else ""
        return f"{first}{last_initial}"
    else:  # "full"
        parts = [p for p in [first, middle, last] if p]
        return " ".join(parts)


# ---------------------------------------------------------------------------
# format_transaction_ref
# ---------------------------------------------------------------------------

def format_transaction_ref(txn_id: Optional[int], prefix: str = "TXN") -> str:
    """
    Format a transaction ID into a consistent display reference.

    Args:
        txn_id: The transaction database ID (integer).
        prefix: Reference prefix string (default "TXN").

    Returns:
        Formatted reference string (e.g. "TXN-000042") or "N/A" if None.
    """
    if txn_id is None:
        return "N/A"

    return f"{prefix}-{int(txn_id):06d}"
