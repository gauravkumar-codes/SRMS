"""Tests for the non-GUI core: security, validators, database migration, auth.

Run from the project folder:   python -m unittest discover -s tests -v
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth          # noqa: E402
import config        # noqa: E402
import db            # noqa: E402
import security      # noqa: E402
import validators as v  # noqa: E402

GOOD_PW = "Tr1ckyPass9"


class TempDbCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_path = config.DB_PATH
        config.DB_PATH = Path(self._tmp.name) / "rms.db"

    def tearDown(self):
        config.DB_PATH = self._old_path
        self._tmp.cleanup()

    def register(self, email, first="Asha", last="Verma", pw=GOOD_PW, answer="Delhi"):
        return auth.register_user(first, last, "9876543210", email,
                                  auth.SECURITY_QUESTIONS[0], answer, pw)

    def make_user(self, email, role):
        res = self.register(email)
        self.assertTrue(res.ok, res.message)
        with db.get_conn() as con:
            con.execute("UPDATE users SET role=? WHERE email=?", (role, email))
        return auth.authenticate(email, GOOD_PW).user


class SecurityTests(unittest.TestCase):
    def test_hash_verify_and_salt(self):
        h1, h2 = security.hash_secret("secret1"), security.hash_secret("secret1")
        self.assertNotEqual(h1, h2)                       # random salt
        self.assertTrue(security.verify_secret("secret1", h1))
        self.assertFalse(security.verify_secret("secret2", h1))
        self.assertFalse(security.verify_secret("secret1", "plaintext"))
        self.assertFalse(security.verify_secret("secret1", h1[:-3] + "AAA"))
        self.assertTrue(security.is_hashed(h1))
        self.assertFalse(security.is_hashed("gauravkumar"))

    def test_answer_normalisation(self):
        self.assertEqual(security.normalize_answer("  New   DELHI "), "new delhi")


class ValidatorTests(unittest.TestCase):
    def test_basic(self):
        self.assertTrue(v.is_valid_email("a@b.co"))
        self.assertFalse(v.is_valid_email("a@b"))
        self.assertTrue(v.is_valid_contact("9876543210"))
        self.assertFalse(v.is_valid_contact("98765432²0"))   # unicode digit trick
        self.assertFalse(v.is_valid_contact("12345"))
        self.assertTrue(v.is_valid_pin("110053"))
        self.assertEqual(v.parse_date("14-6-2026").year, 2026)
        self.assertIsNone(v.parse_date("2026-06-14"))
        self.assertIsNone(v.parse_number("nan"))
        self.assertIsNone(v.parse_number("inf"))
        self.assertEqual(v.parse_number(" 45.5 "), 45.5)
        self.assertEqual(v.fmt_num(4000.0), "4000")
        self.assertEqual(v.fmt_num(66.6667), "66.67")
        self.assertEqual(v.like_pattern("50%_"), "%50\\%\\_%")

    def test_password_policy(self):
        self.assertIsNotNone(v.check_password_policy("short1"))
        self.assertIsNotNone(v.check_password_policy("onlyletters"))
        self.assertIsNotNone(v.check_password_policy("12345678"))
        self.assertIsNotNone(v.check_password_policy("password123"))
        self.assertIsNotNone(v.check_password_policy("asha12345", "asha@x.com"))
        self.assertIsNotNone(v.check_password_policy("Verma2024x", "", ("Verma",)))
        self.assertIsNone(v.check_password_policy(GOOD_PW, "asha@x.com", ("Asha",)) or None
                          if False else v.check_password_policy("Tr1ckyPass9", "q@x.com"))
        self.assertEqual(v.password_strength(""), "")
        self.assertEqual(v.password_strength("abc"), "Weak")
        self.assertEqual(v.password_strength("Tr1ckyPass9!x"), "Strong")


LEGACY_SQL = [
    "CREATE TABLE course (cid INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,duration TEXT,charges TEXT,description TEXT)",
    "CREATE TABLE student (roll INTEGER PRIMARY KEY AUTOINCREMENT,name text,email text,gender text,dob text,contact text,addmission text,course text,state text,city text,pin text,address text)",
    "CREATE TABLE result (rid INTEGER PRIMARY KEY AUTOINCREMENT,roll TEXT,name TEXT,course TEXT,marks_ob TEXT, full_marks TEXT, per TEXT)",
    "CREATE TABLE users ( id INTEGER PRIMARY KEY AUTOINCREMENT, first_name TEXT NOT NULL, last_name TEXT NOT NULL, contact TEXT NOT NULL, email TEXT UNIQUE NOT NULL, security_question TEXT NOT NULL, security_answer TEXT NOT NULL, password TEXT NOT NULL)",
    "INSERT INTO course VALUES (26,'Python','2 Months','4000','Best Course!!')",
    "INSERT INTO course VALUES (27,'Java','3 Months','3000','Another')",
    "INSERT INTO student VALUES (101,'Kaviraj Singh','kavi@gmail.com','Male','02-11-2004','9900778866','07-11-2015','Python','Delhi','Delhi','110053','Ghonda')",
    "INSERT INTO student VALUES (102,'Reema','reema@gmail.com','Female','13-09-2006','8899009988','14-6-2026','Java','Delhi','Delhi','110053','Arvind Nagar')",
    "INSERT INTO student VALUES (103,'No Course','n@x.com','Select','','','','Ghost','','','','')",
    "INSERT INTO result VALUES (13,'101','Kaviraj Singh','Python','89','100','89.0')",
    "INSERT INTO result VALUES (14,'102','Reema','Java','98','100','98.0')",
    "INSERT INTO result VALUES (15,'999','Orphan','Java','10','100','10.0')",
    "INSERT INTO users VALUES (6,'Gaurav','Kumar','9999999999','Gaurav@Gmail.com','Your First School?','Delhi Public','gauravkumar')",
    "INSERT INTO users VALUES (7,'Second','User','8888888888','second@x.com','Your Pet Name?','Tom','plainpass1')",
]


class MigrationTests(TempDbCase):
    def build_legacy(self):
        con = sqlite3.connect(config.DB_PATH)
        for stmt in LEGACY_SQL:
            con.execute(stmt)
        con.commit()
        con.close()

    def test_fresh_database(self):
        self.assertFalse(db.init_db()["migrated"])
        with db.get_conn() as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], db.SCHEMA_VERSION)
            self.assertEqual(con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        self.assertEqual(db.init_db(), {"migrated": False})      # idempotent

    def test_legacy_upgrade_keeps_data(self):
        self.build_legacy()
        summary = db.init_db()
        self.assertTrue(summary["migrated"])
        self.assertTrue((config.DB_PATH.parent / "rms.db.bak-v1").exists())
        with db.get_conn() as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM course").fetchone()[0], 2)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM student").fetchone()[0], 3)
            # orphan result (roll 999) is skipped, the two real ones are kept
            self.assertEqual(con.execute("SELECT COUNT(*) FROM result").fetchone()[0], 2)
            row = con.execute(
                "SELECT s.name, c.name AS course, r.marks_ob, r.full_marks FROM result r "
                "JOIN student s ON s.roll=r.roll JOIN course c ON c.cid=r.course_id "
                "WHERE r.roll=101").fetchone()
            self.assertEqual(tuple(row), ("Kaviraj Singh", "Python", 89.0, 100.0))
            ghost = con.execute("SELECT course_id, gender FROM student WHERE roll=103").fetchone()
            self.assertIsNone(ghost["course_id"])
            self.assertEqual(ghost["gender"], "")             # 'Select' placeholder cleaned
            self.assertEqual(con.execute("SELECT charges FROM course WHERE cid=26").fetchone()[0], 4000.0)

    def test_legacy_users_hashed_and_roles(self):
        self.build_legacy()
        db.init_db()
        with db.get_conn() as con:
            users = con.execute("SELECT id, email, password, security_answer, role "
                                "FROM users ORDER BY id").fetchall()
        self.assertEqual([u["role"] for u in users], ["admin", "viewer"])
        self.assertEqual(users[0]["email"], "gaurav@gmail.com")     # lower-cased
        for u in users:
            self.assertTrue(security.is_hashed(u["password"]))
            self.assertTrue(security.is_hashed(u["security_answer"]))
        # the OLD password still works, and answers are case-insensitive
        self.assertTrue(auth.authenticate("GAURAV@gmail.com", "gauravkumar").ok)
        ok, _ = auth.reset_password("gaurav@gmail.com", "  DELHI public ", "N3wSecret77")
        self.assertTrue(ok)
        self.assertTrue(auth.authenticate("gaurav@gmail.com", "N3wSecret77").ok)

    def test_foreign_keys_enforced(self):
        self.build_legacy()
        db.init_db()
        with db.get_conn() as con:
            with self.assertRaises(sqlite3.IntegrityError):     # course still in use
                con.execute("DELETE FROM course WHERE cid=26")
        with db.get_conn() as con:
            with self.assertRaises(sqlite3.IntegrityError):     # duplicate (roll, course)
                con.execute("INSERT INTO result (roll,course_id,marks_ob,full_marks) VALUES (101,26,5,10)")
        with db.get_conn() as con:
            with self.assertRaises(sqlite3.IntegrityError):     # marks > full marks
                con.execute("INSERT INTO result (roll,course_id,marks_ob,full_marks) VALUES (102,26,50,10)")
        with db.get_conn() as con:
            with self.assertRaises(sqlite3.IntegrityError):     # unknown student
                con.execute("INSERT INTO result (roll,course_id,marks_ob,full_marks) VALUES (555,26,5,10)")
        with db.get_conn() as con:                               # cascade: no orphans
            con.execute("DELETE FROM student WHERE roll=101")
            self.assertEqual(con.execute("SELECT COUNT(*) FROM result WHERE roll=101").fetchone()[0], 0)


class AuthTests(TempDbCase):
    def setUp(self):
        super().setUp()
        db.init_db()

    def test_first_user_admin_then_pending(self):
        r1 = self.register("first@x.com")
        r2 = self.register("second@x.com")
        self.assertEqual((r1.ok, r1.role), (True, "admin"))
        self.assertEqual((r2.ok, r2.role), (True, "pending"))

    def test_registration_validation(self):
        bad = [
            dict(pw="short1"), dict(pw="alllettersss"), dict(pw="password123"),
        ]
        for case in bad:
            self.assertFalse(self.register("a@x.com", **case).ok)
        self.assertFalse(auth.register_user("A", "B", "123", "a@x.com", auth.SECURITY_QUESTIONS[0], "x1", GOOD_PW).ok)
        self.assertFalse(auth.register_user("A", "B", "9876543210", "not-mail", auth.SECURITY_QUESTIONS[0], "ab", GOOD_PW).ok)
        self.assertFalse(auth.register_user("A", "B", "9876543210", "a@x.com", "Select", "ab", GOOD_PW).ok)
        self.assertFalse(auth.register_user("", "B", "9876543210", "a@x.com", auth.SECURITY_QUESTIONS[0], "ab", GOOD_PW).ok)

    def test_email_unique_case_insensitive(self):
        self.assertTrue(self.register("Mixed@Case.com").ok)
        self.assertFalse(self.register("mixed@case.COM").ok)

    def test_nothing_stored_in_plaintext(self):
        self.register("p@x.com", answer="Secret Town")
        with db.get_conn() as con:
            row = con.execute("SELECT password, security_answer FROM users").fetchone()
        self.assertNotIn(GOOD_PW, row["password"])
        self.assertNotIn("secret", row["security_answer"].lower())

    def test_login_flow_and_uniform_errors(self):
        self.register("admin@x.com")
        self.register("pend@x.com")
        self.assertTrue(auth.authenticate("ADMIN@x.com ", GOOD_PW).ok)
        wrong_pw = auth.authenticate("admin@x.com", "Wrong1234")
        unknown = auth.authenticate("ghost@x.com", "Wrong1234")
        self.assertFalse(wrong_pw.ok)
        self.assertEqual(wrong_pw.message, unknown.message)       # no account enumeration
        pend = auth.authenticate("pend@x.com", GOOD_PW)
        self.assertFalse(pend.ok)
        self.assertEqual(pend.message, auth.PENDING_MSG)
        # wrong password for a pending account must NOT reveal it is pending
        self.assertEqual(auth.authenticate("pend@x.com", "Wrong1234").message, auth.INVALID_LOGIN)

    def test_lockout_applies_to_known_and_unknown(self):
        self.register("admin@x.com")
        for email in ("admin@x.com", "ghost@x.com"):
            for _ in range(auth.MAX_ATTEMPTS):
                res = auth.authenticate(email, "Wrong1234")
            self.assertIn("Too many failed attempts", res.message)
            # even the CORRECT password is refused while locked
            self.assertIn("Too many", auth.authenticate(email, GOOD_PW).message)
        # lock expires
        with db.get_conn() as con:
            past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
            con.execute("UPDATE login_attempts SET locked_until=?", (past,))
        self.assertTrue(auth.authenticate("admin@x.com", GOOD_PW).ok)

    def test_success_resets_failure_counter(self):
        self.register("admin@x.com")
        for _ in range(auth.MAX_ATTEMPTS - 1):
            auth.authenticate("admin@x.com", "Wrong1234")
        self.assertTrue(auth.authenticate("admin@x.com", GOOD_PW).ok)
        for _ in range(auth.MAX_ATTEMPTS - 1):
            auth.authenticate("admin@x.com", "Wrong1234")
        self.assertTrue(auth.authenticate("admin@x.com", GOOD_PW).ok)   # still not locked

    def test_password_reset(self):
        self.register("admin@x.com", answer="Delhi")
        q = auth.get_security_question("admin@x.com")
        self.assertEqual(q, auth.SECURITY_QUESTIONS[0])
        fake1, fake2 = auth.get_security_question("ghost@x.com"), auth.get_security_question("ghost@x.com")
        self.assertEqual(fake1, fake2)                                  # stable fake question
        self.assertIn(fake1, auth.SECURITY_QUESTIONS)
        ok, msg = auth.reset_password("admin@x.com", "wrong", "N3wSecret77")
        self.assertEqual((ok, msg), (False, auth.INVALID_RESET))
        self.assertEqual(auth.reset_password("ghost@x.com", "wrong", "N3wSecret77"),
                         (False, auth.INVALID_RESET))
        self.assertFalse(auth.reset_password("admin@x.com", " DELHI ", "weak")[0])   # policy
        self.assertTrue(auth.reset_password("admin@x.com", " DELHI ", "N3wSecret77")[0])
        self.assertFalse(auth.authenticate("admin@x.com", GOOD_PW).ok)
        self.assertTrue(auth.authenticate("admin@x.com", "N3wSecret77").ok)

    def test_reset_is_rate_limited(self):
        self.register("admin@x.com", answer="Delhi")
        for _ in range(auth.MAX_ATTEMPTS):
            res = auth.reset_password("admin@x.com", "guess", "N3wSecret77")
        self.assertIn("Too many", res[1])
        self.assertIn("Too many", auth.reset_password("admin@x.com", "Delhi", "N3wSecret77")[1])

    def test_reset_unlocks_login(self):
        self.register("admin@x.com", answer="Delhi")
        for _ in range(auth.MAX_ATTEMPTS):
            auth.authenticate("admin@x.com", "Wrong1234")
        self.assertTrue(auth.reset_password("admin@x.com", "delhi", "N3wSecret77")[0])
        self.assertTrue(auth.authenticate("admin@x.com", "N3wSecret77").ok)


class AuthorizationTests(TempDbCase):
    def setUp(self):
        super().setUp()
        db.init_db()
        self.admin = self.make_user("admin@x.com", "admin")
        self.teacher = self.make_user("teacher@x.com", "teacher")
        self.viewer = self.make_user("viewer@x.com", "viewer")

    def test_permission_matrix(self):
        self.assertTrue(auth.can(self.admin, "course.write"))
        self.assertFalse(auth.can(self.teacher, "course.write"))
        self.assertTrue(auth.can(self.teacher, "student.write"))
        self.assertFalse(auth.can(self.teacher, "student.delete"))
        self.assertTrue(auth.can(self.teacher, "result.write"))
        self.assertFalse(auth.can(self.viewer, "student.write"))
        self.assertTrue(auth.can(self.viewer, "result.read"))
        self.assertFalse(auth.can(None, "result.read"))
        self.assertFalse(auth.can(self.teacher, "users.manage"))

    def test_role_is_rechecked_in_database(self):
        self.assertTrue(auth.can_now(self.teacher, "student.write"))
        with db.get_conn() as con:                               # demoted after login
            con.execute("UPDATE users SET role='viewer' WHERE id=?", (self.teacher.id,))
        self.assertTrue(auth.can(self.teacher, "student.write"))     # stale session copy
        self.assertFalse(auth.can_now(self.teacher, "student.write"))  # authoritative check
        with db.get_conn() as con:                               # deleted after login
            con.execute("DELETE FROM users WHERE id=?", (self.viewer.id,))
        self.assertFalse(auth.can_now(self.viewer, "result.read"))

    def test_only_admin_manages_users(self):
        self.assertFalse(auth.set_role(self.teacher, self.viewer.id, "admin")[0])
        self.assertFalse(auth.delete_user(self.viewer, self.teacher.id)[0])
        with self.assertRaises(PermissionError):
            auth.list_users(self.viewer)
        self.assertEqual(len(auth.list_users(self.admin)), 3)
        self.assertTrue(auth.set_role(self.admin, self.viewer.id, "teacher")[0])
        self.assertFalse(auth.set_role(self.admin, self.viewer.id, "superuser")[0])

    def test_admin_safety_rails(self):
        self.assertFalse(auth.set_role(self.admin, self.admin.id, "viewer")[0])   # not yourself
        self.assertFalse(auth.delete_user(self.admin, self.admin.id)[0])
        second = self.make_user("admin2@x.com", "admin")
        self.assertTrue(auth.set_role(second, self.admin.id, "viewer")[0])        # allowed: 2 admins
        self.assertFalse(auth.set_role(self.admin, second.id, "viewer")[0])       # demoted admin lost rights
        # the last remaining admin can be neither demoted nor deleted by another admin
        third = self.make_user("t3@x.com", "admin")
        self.assertTrue(auth.delete_user(third, second.id)[0])
        self.assertEqual(auth.delete_user(second, third.id)[0], False)

    def test_unlock_account(self):
        for _ in range(auth.MAX_ATTEMPTS):
            auth.authenticate("viewer@x.com", "Wrong1234")
        self.assertIn("Too many", auth.authenticate("viewer@x.com", GOOD_PW).message)
        self.assertFalse(auth.unlock_account(self.teacher, "viewer@x.com")[0])
        self.assertTrue(auth.unlock_account(self.admin, "viewer@x.com")[0])
        self.assertTrue(auth.authenticate("viewer@x.com", GOOD_PW).ok)


if __name__ == "__main__":
    unittest.main()
