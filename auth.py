"""Authentication, authorization (roles) and account administration.

All security decisions live here, not in the GUI:
  * passwords and security answers are stored as salted scrypt hashes
  * login and password-reset attempts are rate limited (lockout)
  * unknown e-mails and wrong passwords look identical to the caller
  * roles map to permissions, and write operations re-check the role in the
    database, so a demoted or deleted user loses access immediately
"""
import hashlib
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import security
from db import get_conn
from validators import (check_password_policy, is_valid_contact, is_valid_email,
                        normalize_email)

# ---------------------------------------------------------------- constants
MAX_ATTEMPTS = 5
LOCK_MINUTES = 5

SECURITY_QUESTIONS = (
    "Your First School?",
    "Your Pet Name?",
    "Your Birth Place?",
    "Your Favourite Teacher?",
    "Your Childhood Nickname?",
)

ROLES = ("admin", "teacher", "viewer")          # roles an admin can hand out
ALL_ROLES = ROLES + ("pending",)                # 'pending' = registered, not yet approved
ROLE_LABELS = {"admin": "Admin", "teacher": "Teacher", "viewer": "Viewer", "pending": "Pending"}

PERMISSIONS = {
    "admin": {"course.read", "course.write", "student.read", "student.write",
              "student.delete", "result.read", "result.write", "result.delete",
              "users.manage"},
    "teacher": {"course.read", "student.read", "student.write", "result.read",
                "result.write", "result.delete"},
    "viewer": {"course.read", "student.read", "result.read"},
    "pending": set(),
}

INVALID_LOGIN = "Invalid email or password."
INVALID_RESET = "Incorrect email or security answer."
PENDING_MSG = "Your account is awaiting administrator approval."


# ------------------------------------------------------------------ models
@dataclass(frozen=True)
class User:
    id: int
    first_name: str
    last_name: str
    email: str
    role: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role.title())


@dataclass(frozen=True)
class AuthResult:
    ok: bool
    user: "User | None" = None
    message: str = ""


@dataclass(frozen=True)
class RegisterResult:
    ok: bool
    message: str
    role: str = ""


# ------------------------------------------------------------ authorization
def can(user, permission: str) -> bool:
    """Fast check against the role held in the session (use for showing/hiding UI)."""
    return user is not None and permission in PERMISSIONS.get(user.role, set())


def can_now(user, permission: str) -> bool:
    """Authoritative check: re-reads the user's current role from the database.

    Use this before any write. If the user was demoted or deleted after logging
    in, the change takes effect on the very next action.
    """
    if user is None:
        return False
    try:
        with get_conn() as con:
            row = con.execute("SELECT role FROM users WHERE id = ?", (user.id,)).fetchone()
    except sqlite3.Error:
        return False
    return row is not None and permission in PERMISSIONS.get(row["role"], set())


# ------------------------------------------------------------- rate limiting
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _lock_seconds(con, key: str) -> int:
    row = con.execute("SELECT locked_until FROM login_attempts WHERE key = ?", (key,)).fetchone()
    if row and row["locked_until"]:
        remaining = (datetime.fromisoformat(row["locked_until"]) - _now()).total_seconds()
        if remaining > 0:
            return int(math.ceil(remaining))
    return 0


def _record_failure(con, key: str) -> bool:
    """Count a failed attempt; returns True when this failure locks the key."""
    row = con.execute("SELECT failures FROM login_attempts WHERE key = ?", (key,)).fetchone()
    failures = (row["failures"] if row else 0) + 1
    locked_until = None
    if failures >= MAX_ATTEMPTS:
        locked_until = (_now() + timedelta(minutes=LOCK_MINUTES)).isoformat()
        failures = 0
    con.execute(
        "INSERT INTO login_attempts (key, failures, locked_until) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET failures = excluded.failures, "
        "locked_until = excluded.locked_until", (key, failures, locked_until))
    return locked_until is not None


def _clear_failures(con, key: str) -> None:
    con.execute("DELETE FROM login_attempts WHERE key = ?", (key,))


def _lock_message(seconds: int) -> str:
    minutes = max(1, math.ceil(seconds / 60))
    return (f"Too many failed attempts. Please try again in {minutes} "
            f"minute{'s' if minutes != 1 else ''}.")


# ------------------------------------------------------------- registration
def register_user(first, last, contact, email, question, answer, password) -> RegisterResult:
    """Validate and create an account.

    The very first account becomes the administrator. Every later account is
    'pending' until an administrator approves it and assigns a role.
    """
    first, last, contact = (first or "").strip(), (last or "").strip(), (contact or "").strip()
    email, answer = normalize_email(email), (answer or "").strip()

    if not all([first, last, contact, email, question, answer, password]):
        return RegisterResult(False, "All fields are required!")
    if question not in SECURITY_QUESTIONS:
        return RegisterResult(False, "Please choose a security question.")
    if not is_valid_contact(contact):
        return RegisterResult(False, "Enter a valid 10-digit contact number!")
    if not is_valid_email(email):
        return RegisterResult(False, "Enter a valid email address!")
    if len(security.normalize_answer(answer)) < 2:
        return RegisterResult(False, "Security answer is too short.")
    problem = check_password_policy(password, email, (first, last))
    if problem:
        return RegisterResult(False, problem)

    pw_hash = security.hash_secret(password)
    answer_hash = security.hash_secret(security.normalize_answer(answer))
    try:
        with get_conn() as con:
            con.execute("BEGIN IMMEDIATE")      # makes "first user" race-free
            count = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            role = "admin" if count == 0 else "pending"
            con.execute(
                "INSERT INTO users (first_name, last_name, contact, email, "
                "security_question, security_answer, password, role) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (first, last, contact, email, question, answer_hash, pw_hash, role))
    except sqlite3.IntegrityError:
        return RegisterResult(False, "This email is already registered!")
    except sqlite3.Error as ex:
        return RegisterResult(False, f"Database error: {ex}")
    return RegisterResult(True, "Registration completed.", role)


# -------------------------------------------------------------------- login
def authenticate(email, password) -> AuthResult:
    email = normalize_email(email)
    if not email or not password:
        return AuthResult(False, message="Please enter both email and password!")

    key = f"login:{email}"
    try:
        with get_conn() as con:
            remaining = _lock_seconds(con, key)
            if remaining:
                return AuthResult(False, message=_lock_message(remaining))

            row = con.execute(
                "SELECT id, first_name, last_name, email, password, role FROM users "
                "WHERE email = ?", (email,)).fetchone()
            if row is None:
                security.burn_time(password)
                password_ok = False
            else:
                password_ok = security.verify_secret(password, row["password"])

            if not password_ok:
                locked = _record_failure(con, key)
                return AuthResult(False, message=(
                    _lock_message(LOCK_MINUTES * 60) if locked else INVALID_LOGIN))

            _clear_failures(con, key)
            if row["role"] == "pending":
                return AuthResult(False, message=PENDING_MSG)
            return AuthResult(True, User(row["id"], row["first_name"], row["last_name"],
                                         row["email"], row["role"]))
    except sqlite3.Error as ex:
        return AuthResult(False, message=f"Database error: {ex}")


# ----------------------------------------------------------- password reset
def get_security_question(email) -> str:
    """Question to show on the reset form.

    For an unknown e-mail a stable, plausible question is returned instead of an
    error, so the form cannot be used to discover which e-mails are registered.
    """
    email = normalize_email(email)
    with get_conn() as con:
        row = con.execute("SELECT security_question FROM users WHERE email = ?",
                          (email,)).fetchone()
    if row:
        return row["security_question"]
    index = int(hashlib.sha256(email.encode()).hexdigest(), 16) % len(SECURITY_QUESTIONS)
    return SECURITY_QUESTIONS[index]


def reset_password(email, answer, new_password):
    """Returns (ok, message)."""
    email = normalize_email(email)
    if not email or not (answer or "").strip() or not new_password:
        return False, "Please fill in all fields."
    problem = check_password_policy(new_password, email)
    if problem:
        return False, problem

    key = f"reset:{email}"
    try:
        with get_conn() as con:
            remaining = _lock_seconds(con, key)
            if remaining:
                return False, _lock_message(remaining)

            row = con.execute("SELECT id, security_answer FROM users WHERE email = ?",
                              (email,)).fetchone()
            candidate = security.normalize_answer(answer)
            if row is None:
                security.burn_time(candidate)
                answer_ok = False
            else:
                answer_ok = security.verify_secret(candidate, row["security_answer"])

            if not answer_ok:
                locked = _record_failure(con, key)
                return False, _lock_message(LOCK_MINUTES * 60) if locked else INVALID_RESET

            con.execute("UPDATE users SET password = ? WHERE id = ?",
                        (security.hash_secret(new_password), row["id"]))
            _clear_failures(con, key)
            _clear_failures(con, f"login:{email}")   # a reset also unlocks the login
            return True, "Password reset successfully! You can now log in."
    except sqlite3.Error as ex:
        return False, f"Database error: {ex}"


# ------------------------------------------------------ account administration
_DENIED = "You do not have permission to manage users."


def list_users(actor):
    if not can_now(actor, "users.manage"):
        raise PermissionError(_DENIED)
    with get_conn() as con:
        return con.execute(
            "SELECT id, first_name, last_name, email, contact, role, created_at "
            "FROM users ORDER BY (role = 'pending') DESC, id").fetchall()


def _admin_count(con) -> int:
    return con.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]


def set_role(actor, target_id: int, new_role: str):
    """Returns (ok, message)."""
    if not can_now(actor, "users.manage"):
        return False, _DENIED
    if new_role not in ALL_ROLES:
        return False, "Unknown role."
    if actor.id == target_id:
        return False, "You cannot change your own role."
    with get_conn() as con:
        row = con.execute("SELECT role FROM users WHERE id = ?", (target_id,)).fetchone()
        if row is None:
            return False, "User not found."
        if row["role"] == "admin" and new_role != "admin" and _admin_count(con) <= 1:
            return False, "At least one administrator must remain."
        con.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, target_id))
    return True, f"Role updated to {ROLE_LABELS[new_role]}."


def delete_user(actor, target_id: int):
    if not can_now(actor, "users.manage"):
        return False, _DENIED
    if actor.id == target_id:
        return False, "You cannot delete your own account."
    with get_conn() as con:
        row = con.execute("SELECT role FROM users WHERE id = ?", (target_id,)).fetchone()
        if row is None:
            return False, "User not found."
        if row["role"] == "admin" and _admin_count(con) <= 1:
            return False, "At least one administrator must remain."
        con.execute("DELETE FROM users WHERE id = ?", (target_id,))
    return True, "User deleted."


def unlock_account(actor, email: str):
    """Clear login/reset lockouts for an e-mail address."""
    if not can_now(actor, "users.manage"):
        return False, _DENIED
    email = normalize_email(email)
    with get_conn() as con:
        _clear_failures(con, f"login:{email}")
        _clear_failures(con, f"reset:{email}")
    return True, "Login attempts have been reset."
