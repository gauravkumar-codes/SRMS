"""Drives every screen's logic with a stand-in tkinter (see fake_tk.py).

Checks the wiring between the screens, the database and the permission rules for
all three roles. It does not check how the windows LOOK; run the real app for that.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fake_tk                      # noqa: E402
MB = fake_tk.install()              # must happen before the application modules are imported

import auth                         # noqa: E402
import db                           # noqa: E402
from test_core import GOOD_PW, TempDbCase   # noqa: E402
from tkinter import Tk, Toplevel    # noqa: E402  (these are the fakes)

import course, dashboard, forget_password, login, register, report, result, student, users  # noqa: E402,E401


def win():
    return Toplevel(Tk())


def last_error():
    kind, title, message = MB.last()
    return kind, title, message


class GuiBase(TempDbCase):
    def setUp(self):
        super().setUp()
        db.init_db()
        MB.calls.clear()
        MB.answer = True
        self.admin = self.make_user("admin@x.com", "admin")
        self.teacher = self.make_user("teacher@x.com", "teacher")
        self.viewer = self.make_user("viewer@x.com", "viewer")

    def q(self, sql, *args):
        with db.get_conn() as con:
            return [tuple(r) for r in con.execute(sql, args).fetchall()]

    def seed(self):
        with db.get_conn() as con:
            con.execute("INSERT INTO course (name, duration, charges) VALUES ('Python','2 Months',4000)")
            con.execute("INSERT INTO student (roll, name, course_id) VALUES (101,'Kavi',1)")
            con.execute("INSERT INTO result (roll, course_id, marks_ob, full_marks) VALUES (101,1,89,100)")

    def fill_student_form(self, s, roll="201", name="Asha Rao", course_name="Python"):
        for var, val in ((s.var_roll, roll), (s.var_name, name), (s.var_email, "a@b.co"),
                         (s.var_gender, "Female"), (s.var_dob, "5-3-2005"),
                         (s.var_contact, "9876543210"), (s.var_course, course_name),
                         (s.var_state, "Delhi"), (s.var_city, "Delhi"), (s.var_pin, "110053")):
            var.set(val)
        s.txt_address.insert("end", "Arvind Nagar")


class CourseScreen(GuiBase):
    def test_admin_full_cycle(self):
        c = course.CourseClass(win(), self.admin)
        c.var_coursename.set("Math"); c.var_duration.set("1 Month"); c.var_fee.set("1500")
        c.txt_description.insert("end", "Algebra")
        c.add()
        self.assertEqual(self.q("SELECT name, charges, description FROM course"),
                         [("Math", 1500.0, "Algebra")])
        self.assertEqual(MB.last()[0], "showinfo")
        self.assertEqual(c.var_coursename.get(), "")                     # form cleared

        iid = next(iter(c.rows)); c.CourseTable.focus_id = iid; c.get_data(None)
        self.assertEqual((c.var_coursename.get(), c.var_fee.get()), ("Math", "1500"))
        c.var_coursename.set("Maths"); c.update()                        # renaming now works
        self.assertEqual(self.q("SELECT name FROM course"), [("Maths",)])

        c.var_coursename.set("MATHS"); c.var_fee.set("1"); c.selected_cid = None; c.add()
        self.assertEqual(MB.last()[0], "showerror")                      # duplicate (case-insens.)
        c.var_coursename.set("Other"); c.var_fee.set("abc"); c.add()
        self.assertIn("Course Fee", last_error()[2])
        c.var_fee.set("-5"); c.add()
        self.assertIn("Course Fee", last_error()[2])
        self.assertEqual(len(self.q("SELECT * FROM course")), 1)

        c.var_search.set("%"); c.search()                                # wildcard is literal
        self.assertEqual(last_error()[2], "No record found")

    def test_cannot_delete_course_in_use(self):
        self.seed()
        c = course.CourseClass(win(), self.admin)
        iid = next(iter(c.rows)); c.CourseTable.focus_id = iid; c.get_data(None)
        c.delete()
        self.assertEqual(MB.last()[1], "Cannot Delete")
        self.assertEqual(len(self.q("SELECT * FROM course")), 1)

    def test_viewer_and_teacher_are_blocked(self):
        for user in (self.viewer, self.teacher):
            c = course.CourseClass(win(), user)
            self.assertFalse(c.can_write)
            c.var_coursename.set("Hack"); c.var_fee.set("1"); c.add()
            self.assertEqual(MB.last()[1], "Access Denied")
            c.delete()
            self.assertEqual(MB.last()[1], "Access Denied")
        self.assertEqual(self.q("SELECT * FROM course"), [])

    def test_view_only_user_can_still_read_rows(self):
        self.seed()
        c = course.CourseClass(win(), self.viewer)
        iid = next(iter(c.rows)); c.CourseTable.focus_id = iid; c.get_data(None)
        self.assertEqual(c.var_coursename.get(), "Python")
        self.assertEqual(c.txt_description.kw["state"], "disabled")


class StudentScreen(GuiBase):
    def test_add_update_search_delete(self):
        self.seed()
        s = student.StudentClass(win(), self.teacher)
        self.fill_student_form(s)
        s.add()
        row = self.q("SELECT roll, name, dob, admission, course_id, gender, address FROM student WHERE roll=201")[0]
        self.assertEqual(row[:3], (201, "Asha Rao", "05-03-2005"))        # date normalised
        self.assertEqual((row[4], row[5], row[6]), (1, "Female", "Arvind Nagar"))
        self.assertTrue(row[3])                                          # defaulted to today
        self.assertEqual(MB.last()[0], "showinfo")

        s.var_search.set("asha"); s.search()
        self.assertEqual([v[1] for v in s.StudentTable.items.values()], ["Asha Rao"])
        s.clear()
        iid = [k for k, v in s.rows.items() if v[0] == 201][0]
        s.StudentTable.focus_id = iid; s.get_data(None)
        self.assertEqual((s.var_course.get(), s.var_dob.get()), ("Python", "05-03-2005"))
        s.var_city.set("Noida"); s.update()
        self.assertEqual(self.q("SELECT city FROM student WHERE roll=201"), [("Noida",)])

        s.StudentTable.focus_id = iid; s.get_data(None); s.delete()      # teacher cannot delete
        self.assertEqual(MB.last()[1], "Access Denied")
        self.assertEqual(len(self.q("SELECT * FROM student WHERE roll=201")), 1)

    def test_validation_messages(self):
        self.seed()
        s = student.StudentClass(win(), self.admin)
        cases = [("roll", "x1", "Roll No."), ("roll", "0", "Roll No."), ("name", " ", "Name"),
                 ("email", "bad", "email"), ("contact", "123", "Contact"), ("pin", "12", "Pin"),
                 ("dob", "31-02-2000", "D.O.B"), ("dob", "01-01-2999", "past"),
                 ("course", "Select", "course")]
        for field, bad, expect in cases:
            self.fill_student_form(s); getattr(s, f"var_{field}").set(bad)
            MB.calls.clear(); s.add()
            self.assertEqual(MB.last()[0], "showerror", field)
            self.assertIn(expect, MB.last()[2], field)
            s.txt_address.content = ""
        self.assertEqual(len(self.q("SELECT * FROM student")), 1)        # only the seeded one

    def test_duplicate_roll_and_cascade_warning(self):
        self.seed()
        s = student.StudentClass(win(), self.admin)
        self.fill_student_form(s, roll="101"); s.add()
        self.assertIn("already present", MB.last()[2])
        iid = [k for k, v in s.rows.items() if v[0] == 101][0]
        s.StudentTable.focus_id = iid; s.get_data(None)
        MB.calls.clear(); s.delete()
        confirm = [c for c in MB.calls if c[0] == "askyesno"][0]
        self.assertIn("also delete 1 result", confirm[2])
        self.assertEqual(self.q("SELECT * FROM student"), [])
        self.assertEqual(self.q("SELECT * FROM result"), [])             # no orphans

    def test_viewer_blocked(self):
        self.seed()
        s = student.StudentClass(win(), self.viewer)
        self.fill_student_form(s); s.add()
        self.assertEqual(MB.last()[1], "Access Denied")
        self.assertEqual(len(self.q("SELECT * FROM student")), 1)

    def test_new_course_appears_without_reopening(self):
        self.seed()
        s = student.StudentClass(win(), self.admin)
        with db.get_conn() as con:
            con.execute("INSERT INTO course (name) VALUES ('Java')")
        s.refresh_course_values()
        self.assertIn("Java", s.txt_course["values"])


class ResultScreen(GuiBase):
    def test_add_result_flow(self):
        self.seed()
        with db.get_conn() as con:
            con.execute("INSERT INTO course (name) VALUES ('Java')")
            con.execute("INSERT INTO student (roll, name, course_id) VALUES (102,'Reema',2)")
            con.execute("INSERT INTO student (roll, name, course_id) VALUES (103,'NoCourse',NULL)")
        r = result.ResultClass(win(), self.teacher)
        r.add()
        self.assertIn("first search", MB.last()[2])
        r.var_roll.set("102"); r.search()
        self.assertEqual((r.var_name.get(), r.var_course.get()), ("Reema", "Java"))
        for marks, full, expect in (("x", "100", "numbers"), ("50", "0", "greater"),
                                    ("120", "100", "between"), ("-1", "100", "between"),
                                    ("nan", "100", "numbers")):
            r.var_marks.set(marks); r.var_full_marks.set(full); r.add()
            self.assertIn(expect, MB.last()[2], (marks, full))
        r.var_marks.set("45.5"); r.var_full_marks.set("50")
        self.assertEqual(r.var_percent.get(), "91.00%")                  # live preview
        r.add()
        self.assertEqual(self.q("SELECT roll, course_id, marks_ob, full_marks FROM result WHERE roll=102"),
                         [(102, 2, 45.5, 50.0)])
        self.assertEqual(r.var_roll.get(), "Select")                     # form cleared
        r.var_roll.set("102"); r.search(); r.var_marks.set("1"); r.var_full_marks.set("2"); r.add()
        self.assertIn("already present", MB.last()[2])                   # unique (roll, course)
        r.var_roll.set("103"); r.search()
        self.assertIn("no course", MB.last()[2])

    def test_viewer_blocked(self):
        self.seed()
        r = result.ResultClass(win(), self.viewer)
        r.var_roll.set("101"); r.search(); r.var_marks.set("1"); r.var_full_marks.set("2"); r.add()
        self.assertEqual(MB.last()[1], "Access Denied")
        self.assertEqual(len(self.q("SELECT * FROM result")), 1)


class ReportScreen(GuiBase):
    def test_search_show_and_delete(self):
        self.seed()
        with db.get_conn() as con:
            con.execute("INSERT INTO course (name) VALUES ('Java')")
            con.execute("INSERT INTO result (roll, course_id, marks_ob, full_marks) VALUES (101,2,45,60)")
        rep = report.ReportClass(win(), self.teacher)
        rep.var_search.set(""); rep.search(); self.assertIn("required", MB.last()[2])
        rep.var_search.set("abc"); rep.search(); self.assertIn("number", MB.last()[2])
        rep.var_search.set("999"); rep.search(); self.assertEqual(MB.last()[2], "No record found")
        rep.var_search.set("101"); rep.search()
        self.assertEqual(len(rep.ResultTable.items), 2)                  # all results shown
        self.assertEqual(sorted(v[3] for v in rep.ResultTable.items.values()), ["75.00%", "89.00%"])
        iid = [k for k, v in rep.rows.items() if v[3] == "Java"][0]
        rep.ResultTable.selected = (iid,); rep.on_select()
        self.assertEqual((rep.course.kw["text"], rep.per.kw["text"]), ("Java", "75.00%"))
        rep.delete()                                                     # deletes the SELECTED one
        self.assertEqual(self.q("SELECT course_id FROM result"), [(1,)])
        self.assertEqual(len(rep.ResultTable.items), 1)                  # list refreshed

    def test_viewer_has_no_delete_button_and_is_blocked(self):
        self.seed()
        rep = report.ReportClass(win(), self.viewer)
        self.assertFalse(rep.can_delete)
        rep.var_search.set("101"); rep.search()
        rep.delete()
        self.assertEqual(MB.last()[1], "Access Denied")
        self.assertEqual(len(self.q("SELECT * FROM result")), 1)


class UsersScreen(GuiBase):
    def test_admin_approves_and_manages(self):
        pend = self.register("new@x.com"); self.assertEqual(pend.role, "pending")
        u = users.UserAdminClass(win(), self.admin)
        self.assertEqual(len(u.UserTable.items), 4)
        self.assertIn("1 awaiting approval", u.lbl_count.kw["text"])
        iid = [k for k, v in u.rows.items() if v[3] == "new@x.com"][0]
        u.UserTable.focus_id = iid; u.on_select()
        u.var_role.set("teacher"); u.apply_role()
        self.assertEqual(self.q("SELECT role FROM users WHERE email='new@x.com'"), [("teacher",)])
        self.assertTrue(auth.authenticate("new@x.com", GOOD_PW).ok)       # can log in now
        u.apply_role()                                                    # row selection reset
        self.assertIn("Select a user", MB.last()[2])

    def test_non_admin_cannot_open(self):
        u = users.UserAdminClass(win(), self.teacher)
        self.assertEqual(MB.calls[-1][1], "Access Denied")


class DashboardScreen(GuiBase):
    def menu_texts(self, user):
        before = len(fake_tk.Widget.instances)
        dash = dashboard.RMS(Tk(), user)
        texts = [str(w.kw.get("text", "")) for w in fake_tk.Widget.instances[before:]
                 if type(w).__name__ == "Label"]
        return dash, texts

    def has(self, texts, needle):
        return any(needle in t for t in texts)

    def test_menu_depends_on_role(self):
        _, admin_t = self.menu_texts(self.admin)
        _, teacher_t = self.menu_texts(self.teacher)
        _, viewer_t = self.menu_texts(self.viewer)
        for needle in ("Course", "Student", "Result", "View Results", "Users"):
            self.assertTrue(self.has(admin_t, needle), needle)
        self.assertTrue(self.has(teacher_t, "📝  Result"))
        self.assertFalse(self.has(teacher_t, "Users"))
        self.assertFalse(self.has(viewer_t, "📝  Result"))
        self.assertFalse(self.has(viewer_t, "Users"))
        self.assertTrue(self.has(viewer_t, "View Results"))
        self.assertTrue(self.has(admin_t, "Asha"))                       # real name, not "Admin"

    def test_one_window_per_module_and_counts(self):
        self.seed()
        dash, _ = self.menu_texts(self.admin)
        before = fake_tk.Widget.toplevels
        dash.open_module("course", course.CourseClass)
        dash.open_module("course", course.CourseClass)                   # second click: reuse
        self.assertEqual(fake_tk.Widget.toplevels - before, 1)
        dash.windows["course"][0].destroy()
        dash.open_module("course", course.CourseClass)                   # closed -> open a new one
        self.assertEqual(fake_tk.Widget.toplevels - before, 2)
        self.assertEqual(dash.lbl_student.kw["text"], "1")
        self.assertEqual(dash.lbl_result.kw["text"], "1")
        self.register("p@x.com")
        dash.update_counts()
        self.assertIn("(1)", dash.btn_users.kw["text"])                  # pending badge

    def test_logout_and_exit(self):
        dash, _ = self.menu_texts(self.admin)
        MB.answer = False; dash.logout()
        self.assertEqual(dash.next_screen, (None, None))
        MB.answer = True; dash.logout()
        self.assertEqual(dash.next_screen, ("login", None))


def fill(entry, text):
    entry.delete(0, "end")
    entry.insert(0, text)


class AuthScreens(GuiBase):
    def test_login_screen(self):
        lg = login.Login(Tk())
        fill(lg.txt_email, "ADMIN@x.com"); fill(lg.txt_password, "wrong-pass1")
        lg.login_data()
        self.assertEqual(MB.last()[2], auth.INVALID_LOGIN)
        self.assertEqual(lg.txt_password.get(), "")                      # password wiped
        self.assertEqual(lg.next_screen, (None, None))
        fill(lg.txt_email, "admin@x.com"); fill(lg.txt_password, GOOD_PW)
        lg.login_data()
        self.assertEqual(lg.next_screen[0], "dashboard")
        self.assertEqual(lg.next_screen[1].role, "admin")
        lg2 = login.Login(Tk()); lg2.open_register()
        self.assertEqual(lg2.next_screen, ("register", None))

    def test_pending_user_is_told_to_wait(self):
        self.register("wait@x.com")
        lg = login.Login(Tk())
        fill(lg.txt_email, "wait@x.com"); fill(lg.txt_password, GOOD_PW)
        lg.login_data()
        self.assertEqual(MB.last()[2], auth.PENDING_MSG)

    def fill_register(self, rg, email, pw=GOOD_PW, confirm=None):
        fill(rg.txt_fname, "Neha"); fill(rg.txt_lname, "Singh"); fill(rg.txt_contact, "9876543210")
        fill(rg.txt_email, email); fill(rg.txt_answer, "Delhi")
        rg.cmb_quest.set(auth.SECURITY_QUESTIONS[1])
        fill(rg.txt_password, pw); fill(rg.txt_cpassword, pw if confirm is None else confirm)
        rg.var_check.set(1)

    def test_register_screen(self):
        rg = register.Register(Tk())
        self.fill_register(rg, "n@x.com", confirm="Different1"); rg.register_data()
        self.assertIn("do not match", MB.last()[2])
        self.fill_register(rg, "n@x.com", pw="weak"); rg.register_data()
        self.assertEqual(MB.last()[0], "showerror")
        self.fill_register(rg, "n@x.com"); rg.var_check.set(0); rg.register_data()
        self.assertIn("Terms", MB.last()[2])
        rg.var_check.set(1); rg.register_data()
        self.assertEqual(MB.last()[0], "showinfo")
        self.assertIn("approve", MB.last()[2])                           # not the first user
        self.assertEqual(rg.next_screen, ("login", None))
        self.assertEqual(self.q("SELECT role FROM users WHERE email='n@x.com'"), [("pending",)])
        rg.txt_password.insert(0, "Tr1ckyPass9!x"); rg.update_strength()
        self.assertIn("Strong", rg.lbl_strength.kw["text"])

    def test_forgot_password_window(self):
        before = len(fake_tk.Widget.instances)
        forget_password.ForgetPassword(Tk()).forget_password()
        mine = fake_tk.Widget.instances[before:]
        entries = [w for w in mine if type(w).__name__ == "Entry"]
        email_e, answer_e, pw_e = entries
        btn = lambda text: [w for w in mine if type(w).__name__ == "Label" and text in str(w.kw.get("text", ""))][0]
        qlabel = btn("Load your question")

        btn("RESET PASSWORD  →").click()                                    # question not loaded yet
        self.assertIn("load your security question", MB.last()[2])
        fill(email_e, "admin@x.com"); btn("GET SECURITY").click()
        self.assertEqual(qlabel.kw["text"], auth.SECURITY_QUESTIONS[0])
        fill(email_e, "someone-else@x.com")                              # editing the email...
        self.assertIn("Load your question", qlabel.kw["text"])           # ...forgets the question
        fill(email_e, "admin@x.com"); btn("GET SECURITY").click()
        fill(answer_e, "wrong"); fill(pw_e, "N3wSecret77"); btn("RESET PASSWORD  →").click()
        self.assertEqual(MB.last()[2], auth.INVALID_RESET)
        fill(answer_e, "  delhi "); btn("RESET PASSWORD  →").click()
        self.assertEqual(MB.last()[0], "showinfo")
        self.assertTrue(auth.authenticate("admin@x.com", "N3wSecret77").ok)


if __name__ == "__main__":
    unittest.main()
