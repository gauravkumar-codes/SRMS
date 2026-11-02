"""Small, dependency-free input validators and formatters."""
import math
import re
from datetime import datetime

DATE_FORMAT = "%d-%m-%Y"
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

COMMON_PASSWORDS = frozenset({
    "password", "password1", "password12", "password123", "passw0rd", "12345678",
    "123456789", "1234567890", "11111111", "qwerty123", "qwertyuiop", "abc12345",
    "iloveyou", "admin123", "admin1234", "welcome1", "welcome123", "letmein123",
    "monkey123", "dragon123", "football1", "baseball1", "sunshine1", "princess1",
    "changeme1", "test1234", "india123", "student123", "p@ssw0rd", "qwerty12",
})


def normalize_email(email) -> str:
    return (email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    return len(email) <= 254 and bool(EMAIL_RE.fullmatch(email))


def _ascii_digits(text: str, length: int) -> bool:
    # str.isdigit() alone accepts characters such as '²', so require ASCII too
    return len(text) == length and text.isascii() and text.isdigit()


def is_valid_contact(contact: str) -> bool:
    return _ascii_digits(contact, 10)


def is_valid_pin(pin: str) -> bool:
    return _ascii_digits(pin, 6)


def parse_date(text):
    """DD-MM-YYYY -> date, or None when invalid."""
    try:
        return datetime.strptime((text or "").strip(), DATE_FORMAT).date()
    except ValueError:
        return None


def format_date(value) -> str:
    return value.strftime(DATE_FORMAT)


def parse_number(text):
    """Text -> finite float, or None ('nan' and 'inf' are rejected)."""
    try:
        value = float(str(text).strip())
    except (ValueError, TypeError):
        return None
    return value if math.isfinite(value) else None


def fmt_num(value) -> str:
    """4000.0 -> '4000', 87.5 -> '87.5', 66.6667 -> '66.67'."""
    try:
        number = float(value)
    except (ValueError, TypeError):
        return "" if value is None else str(value)
    if number == int(number):
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def like_pattern(text: str) -> str:
    """Escape % and _ so user text is matched literally (use with ESCAPE '\\')."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def check_password_policy(password: str, email: str = "", names=()):
    """Return an error message, or None when the password is acceptable."""
    if len(password) < 8:
        return "Password must contain at least 8 characters."
    if len(password) > 128:
        return "Password must not be longer than 128 characters."
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        return "Password must contain at least one letter and one number."
    lowered = password.lower()
    if lowered in COMMON_PASSWORDS:
        return "That password is too common. Choose a less predictable one."
    local = email.split("@")[0].lower()
    if len(local) >= 3 and local in lowered:
        return "Password must not contain your email name."
    for name in names:
        if len(name) >= 3 and name.lower() in lowered:
            return "Password must not contain your name."
    return None


def password_strength(password: str) -> str:
    """'' / 'Weak' / 'Fair' / 'Strong' for the live strength hint."""
    if not password:
        return ""
    score = sum([
        len(password) >= 8,
        len(password) >= 12,
        any(c.islower() for c in password) and any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ])
    if password.lower() in COMMON_PASSWORDS:
        score = min(score, 1)
    return "Weak" if score <= 2 else "Fair" if score == 3 else "Strong"
