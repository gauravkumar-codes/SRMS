"""Database layer: connections, schema and the one-time upgrade from the old layout.

Schema version 2 fixes the data-model problems of the original project:
  * foreign keys are enforced (PRAGMA foreign_keys = ON on every connection)
  * students and results point at a course by id, not by its name
  * deleting a student deletes that student's results (no orphans)
  * deleting a course that is still in use is refused (RESTRICT)
  * roll numbers are INTEGER everywhere, marks are REAL, and the percentage is
    computed instead of stored
  * one result per (student, course) is enforced by a UNIQUE constraint
  * e-mail is unique case-insensitively
"""
import logging
import shutil
import sqlite3
from contextlib import contextmanager

import config
import security
from validators import normalize_email, parse_number

log = logging.getLogger("srms.db")

SCHEMA_VERSION = 2
LEGACY_TABLES = ("course", "student", "result", "users")

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        contact TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        security_question TEXT NOT NULL,
        security_answer TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'pending'
            CHECK (role IN ('admin', 'teacher', 'viewer', 'pending')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS login_attempts (
        key TEXT PRIMARY KEY,
        failures INTEGER NOT NULL DEFAULT 0,
        locked_until TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS course (
        cid INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        duration TEXT,
        charges REAL NOT NULL DEFAULT 0 CHECK (charges >= 0),
        description TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS student (
        roll INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT,
        gender TEXT,
        dob TEXT,
        contact TEXT,
        admission TEXT,
        course_id INTEGER REFERENCES course(cid) ON DELETE RESTRICT ON UPDATE CASCADE,
        state TEXT,
        city TEXT,
        pin TEXT,
        address TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS result (
        rid INTEGER PRIMARY KEY AUTOINCREMENT,
        roll INTEGER NOT NULL REFERENCES student(roll) ON DELETE CASCADE ON UPDATE CASCADE,
        course_id INTEGER NOT NULL REFERENCES course(cid) ON DELETE RESTRICT ON UPDATE CASCADE,
        marks_ob REAL NOT NULL CHECK (marks_ob >= 0),
        full_marks REAL NOT NULL CHECK (full_marks > 0),
        CHECK (marks_ob <= full_marks),
        UNIQUE (roll, course_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_student_course ON student(course_id)",
    "CREATE INDEX IF NOT EXISTS idx_result_roll ON result(roll)",
]


@contextmanager
def get_conn():
    """Connection with foreign keys on; commits on success, rolls back on error."""
    con = sqlite3.connect(config.DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    """Create the schema, or upgrade an old database in place (backup first).

    Returns a small summary dict (useful for logging and tests).
    """
    path = config.DB_PATH
    con = sqlite3.connect(path, isolation_level=None, timeout=10)  # manual transactions
    summary = {"migrated": False}
    try:
        con.execute("PRAGMA foreign_keys = OFF")  # required while rebuilding tables
        if con.execute("PRAGMA user_version").fetchone()[0] >= SCHEMA_VERSION:
            return summary

        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        legacy = [t for t in LEGACY_TABLES if t in tables]

        if legacy:
            backup = path.with_name(path.name + ".bak-v1")
            if not backup.exists():
                shutil.copy2(path, backup)
                log.info("Backed up old database to %s", backup)

        con.execute("BEGIN")
        try:
            for table in legacy:
                con.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
            for statement in SCHEMA:
                con.execute(statement)
            if legacy:
                summary = _copy_legacy_data(con, legacy)
                for table in legacy:
                    con.execute(f"DROP TABLE {table}_old")
            con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        return summary
    finally:
        con.close()


def _copy_legacy_data(con, legacy):
    """Copy rows from the *_old tables into the new schema."""
    summary = {"migrated": True, "courses": 0, "students": 0, "results": 0,
               "users": 0, "skipped": 0}
    course_ids = {}

    if "course" in legacy:
        for cid, name, duration, charges, description in con.execute(
                "SELECT cid, name, duration, charges, description FROM course_old ORDER BY cid"):
            name = (name or "").strip()
            if not name or name.lower() in course_ids:
                summary["skipped"] += 1
                continue
            fee = parse_number(charges)
            fee = fee if fee is not None and fee >= 0 else 0.0
            con.execute("INSERT INTO course (cid, name, duration, charges, description) "
                        "VALUES (?, ?, ?, ?, ?)", (cid, name, duration, fee, description))
            course_ids[name.lower()] = cid
            summary["courses"] += 1

    rolls = set()
    if "student" in legacy:
        for (roll, name, email, gender, dob, contact, admission, course, state, city,
             pin, address) in con.execute(
                "SELECT roll, name, email, gender, dob, contact, addmission, course, state, "
                "city, pin, address FROM student_old ORDER BY roll"):
            gender = "" if gender in (None, "Select") else gender
            con.execute(
                "INSERT INTO student (roll, name, email, gender, dob, contact, admission, "
                "course_id, state, city, pin, address) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (roll, (name or "").strip() or "Unknown", email, gender, dob, contact,
                 admission, course_ids.get((course or "").strip().lower()), state, city,
                 pin, (address or "").strip()))
            rolls.add(roll)
            summary["students"] += 1

    if "result" in legacy:
        for _rid, roll, _name, course, marks, full, _per in con.execute(
                "SELECT rid, roll, name, course, marks_ob, full_marks, per FROM result_old "
                "ORDER BY rid"):
            try:
                roll = int(str(roll).strip())
            except ValueError:
                roll = None
            cid = course_ids.get((course or "").strip().lower())
            marks, full = parse_number(marks), parse_number(full)
            valid = (roll in rolls and cid is not None and marks is not None
                     and full is not None and full > 0 and 0 <= marks <= full)
            if not valid:
                summary["skipped"] += 1
                log.warning("Skipped unusable legacy result row for roll %r", roll)
                continue
            cur = con.execute(
                "INSERT OR IGNORE INTO result (roll, course_id, marks_ob, full_marks) "
                "VALUES (?, ?, ?, ?)", (roll, cid, marks, full))
            summary["results" if cur.rowcount else "skipped"] += 1

    if "users" in legacy:
        for (uid, first, last, contact, email, question, answer, password) in con.execute(
                "SELECT id, first_name, last_name, contact, email, security_question, "
                "security_answer, password FROM users_old ORDER BY id"):
            if not security.is_hashed(password):
                password = security.hash_secret(password)
            if not security.is_hashed(answer):
                answer = security.hash_secret(security.normalize_answer(answer))
            # least privilege: the oldest account becomes admin, the others viewers
            role = "admin" if summary["users"] == 0 else "viewer"
            try:
                con.execute(
                    "INSERT INTO users (id, first_name, last_name, contact, email, "
                    "security_question, security_answer, password, role) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (uid, first, last, contact, normalize_email(email), question, answer,
                     password, role))
                summary["users"] += 1
            except sqlite3.IntegrityError:
                summary["skipped"] += 1
                log.warning("Skipped user %r (duplicate e-mail after lower-casing)", email)

    return summary
