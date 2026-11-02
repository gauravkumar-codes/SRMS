from tkinter import *
from tkinter import ttk, messagebox
import sqlite3
from datetime import date

import auth
from db import get_conn
from theme import (BLUE, BLUE_HOVER, BORDER, CARD_BG, FIELD_BG, FONT, GREEN, GREEN_HOVER,
                   GREY, GREY_HOVER, MUTED, NAVY, PAGE_BG, RED, RED_HOVER, STRIPE,
                   apply_theme)
from validators import (format_date, is_valid_contact, is_valid_email, is_valid_pin,
                        like_pattern, parse_date)
from widgets import (card_title, make_button, make_card, make_entry, make_label,
                     page_header, require_permission)

# Selected the same way everywhere so the table always shows the course *name*.
STUDENT_SELECT = (
    "SELECT s.roll, s.name, s.email, s.gender, s.dob, s.contact, s.admission, "
    "COALESCE(c.name, ''), s.state, s.city, s.pin, s.address "
    "FROM student s LEFT JOIN course c ON c.cid = s.course_id")


class StudentClass:
    def __init__(self, root, user):
        self.root = root
        self.user = user
        self.can_write = auth.can(user, "student.write")
        self.can_delete = auth.can(user, "student.delete")
        self.rows = {}                      # tree item id -> full row
        self.courses = {}                   # course name -> course id
        self.selected_roll = None

        self.root.title("Student Result Management System")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.minsize(1100, 650)
        self.root.config(bg=PAGE_BG)
        self.root.focus_force()

        apply_theme(self.root)
        self.setup_variables()
        self.refresh_courses()

        page_header(self.root, "🎓  MANAGE STUDENT DETAILS",
                    "Add  •  Update  •  Delete  •  Search" if self.can_write
                    else "View only")
        self.build_body()
        self.clear()

    def setup_variables(self):
        self.var_roll = StringVar()
        self.var_name = StringVar()
        self.var_email = StringVar()
        self.var_gender = StringVar(value="Select")
        self.var_dob = StringVar()
        self.var_contact = StringVar()
        self.var_admission = StringVar()
        self.var_course = StringVar(value="Select")
        self.var_state = StringVar()
        self.var_city = StringVar()
        self.var_pin = StringVar()
        self.var_search = StringVar()

    # ==================== BODY ====================
    def build_body(self):
        body = Frame(self.root, bg=PAGE_BG)
        body.pack(side=TOP, fill=BOTH, expand=True, padx=15, pady=15)
        body.columnconfigure(0, weight=2, uniform="cols")
        body.columnconfigure(1, weight=3, uniform="cols")
        body.rowconfigure(0, weight=1)
        self.build_form(body)
        self.build_table(body)

    def build_form(self, parent):
        card = make_card(parent)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        card_title(card, "Student Information").pack(anchor="w", padx=18, pady=(16, 10))

        form = Frame(card, bg=CARD_BG)
        form.pack(fill=BOTH, expand=True, padx=18)
        form.columnconfigure(1, weight=1, uniform="f")
        form.columnconfigure(3, weight=1, uniform="f")
        ro = not self.can_write

        def pair(row, col, label, widget):
            make_label(form, label).grid(row=row, column=col, sticky="w",
                                         padx=(0, 8) if col == 0 else (16, 8), pady=7)
            widget.grid(row=row, column=col + 1, sticky="ew", ipady=4, pady=7)

        self.txt_roll = make_entry(form, self.var_roll, readonly=ro)
        pair(0, 0, "Roll No.", self.txt_roll)
        pair(1, 0, "Name", make_entry(form, self.var_name, readonly=ro))
        pair(2, 0, "Email", make_entry(form, self.var_email, readonly=ro))
        self.txt_gender = ttk.Combobox(form, textvariable=self.var_gender, state="disabled" if ro else "readonly",
                                       values=("Select", "Male", "Female", "Others"),
                                       font=(FONT, 12), style="Srms.TCombobox")
        pair(3, 0, "Gender", self.txt_gender)

        pair(0, 2, "D.O.B", make_entry(form, self.var_dob, readonly=ro))
        pair(1, 2, "Contact", make_entry(form, self.var_contact, readonly=ro))
        pair(2, 2, "Add. Date", make_entry(form, self.var_admission, readonly=ro))
        self.txt_course = ttk.Combobox(form, textvariable=self.var_course,
                                       state="disabled" if ro else "readonly",
                                       values=["Select"] + sorted(self.courses),
                                       postcommand=self.refresh_course_values,
                                       font=(FONT, 12), style="Srms.TCombobox")
        pair(3, 2, "Course", self.txt_course)

        pair(4, 0, "State", make_entry(form, self.var_state, readonly=ro))
        pair(4, 2, "City", make_entry(form, self.var_city, readonly=ro))
        pair(5, 0, "Pin Code", make_entry(form, self.var_pin, readonly=ro))
        Label(form, text="Dates use DD-MM-YYYY", font=(FONT, 11), bg=CARD_BG, fg=MUTED
              ).grid(row=5, column=2, columnspan=2, sticky="w", padx=(16, 0))

        make_label(form, "Address").grid(row=6, column=0, sticky="nw", pady=9)
        self.txt_address = Text(form, font=(FONT, 12), bg=FIELD_BG, fg=NAVY, height=4,
                                relief=FLAT, highlightthickness=1,
                                highlightbackground=BORDER, highlightcolor=BLUE,
                                insertbackground=NAVY, insertwidth=2, wrap=WORD,
                                state=DISABLED if ro else NORMAL)
        self.txt_address.grid(row=6, column=1, columnspan=3, sticky="nsew", pady=7)
        form.rowconfigure(6, weight=1)

        btns = Frame(card, bg=CARD_BG)
        btns.pack(fill=X, padx=18, pady=(8, 18))
        if ro:
            Label(btns, text="👁  View only — your role cannot modify students",
                  font=(FONT, 12), bg=CARD_BG, fg=MUTED).pack(anchor="w")
            return
        specs = [("💾  Save", self.add, GREEN, GREEN_HOVER),
                 ("✏️  Update", self.update, BLUE, BLUE_HOVER)]
        if self.can_delete:
            specs.append(("🗑  Delete", self.delete, RED, RED_HOVER))
        specs.append(("🧹  Clear", self.clear, GREY, GREY_HOVER))
        for i, (text, cmd, bg, hov) in enumerate(specs):
            btns.columnconfigure(i, weight=1, uniform="btn")
            make_button(btns, text, cmd, bg, hov).grid(
                row=0, column=i, sticky="ew",
                padx=(0 if i == 0 else 6, 0 if i == len(specs) - 1 else 6))

    def build_table(self, parent):
        card = make_card(parent)
        card.grid(row=0, column=1, sticky="nsew")

        top = Frame(card, bg=CARD_BG)
        top.pack(fill=X, padx=18, pady=(16, 10))
        card_title(top, "Student Records").pack(side=LEFT)
        self.lbl_count = Label(top, text="0 records", font=(FONT, 11), bg=CARD_BG, fg=MUTED)
        self.lbl_count.pack(side=RIGHT)

        search = Frame(card, bg=PAGE_BG)
        search.pack(fill=X, padx=18, pady=(0, 10))
        Label(search, text="🔍  Roll No. / Name", font=(FONT, 12, "bold"), bg=PAGE_BG,
              fg=NAVY).pack(side=LEFT, padx=(10, 10), pady=10)
        txt_search = make_entry(search, self.var_search)
        txt_search.pack(side=LEFT, fill=X, expand=True, ipady=4, pady=10)
        txt_search.bind("<Return>", lambda e: self.search())
        make_button(search, "Search", self.search, BLUE, BLUE_HOVER
                    ).pack(side=LEFT, padx=(10, 6), pady=10, ipadx=14)
        make_button(search, "Show All", self.show, GREY, GREY_HOVER
                    ).pack(side=LEFT, padx=(0, 10), pady=10, ipadx=10)

        wrap = Frame(card, bg=CARD_BG)
        wrap.pack(fill=BOTH, expand=True, padx=18, pady=(0, 18))
        scrolly = ttk.Scrollbar(wrap, orient=VERTICAL)
        scrollx = ttk.Scrollbar(wrap, orient=HORIZONTAL)
        cols = ("roll", "name", "email", "gender", "dob", "contact", "admission",
                "course", "state", "city", "pin", "address")
        self.StudentTable = ttk.Treeview(wrap, columns=cols, show="headings",
                                         style="Srms.Treeview",
                                         xscrollcommand=scrollx.set,
                                         yscrollcommand=scrolly.set)
        scrolly.config(command=self.StudentTable.yview)
        scrollx.config(command=self.StudentTable.xview)
        scrolly.pack(side=RIGHT, fill=Y)
        scrollx.pack(side=BOTTOM, fill=X)
        self.StudentTable.pack(fill=BOTH, expand=True)

        headings = {"roll": ("Roll No.", 80), "name": ("Name", 140), "email": ("Email", 190),
                    "gender": ("Gender", 80), "dob": ("D.O.B", 100), "contact": ("Contact", 120),
                    "admission": ("Admission", 110), "course": ("Course", 130),
                    "state": ("State", 110), "city": ("City", 110), "pin": ("Pin Code", 90),
                    "address": ("Address", 220)}
        for key, (text, width) in headings.items():
            self.StudentTable.heading(key, text=text)
            self.StudentTable.column(key, width=width, minwidth=60, anchor="w")
        self.StudentTable.tag_configure("odd", background=STRIPE)
        self.StudentTable.tag_configure("even", background="white")
        self.StudentTable.bind("<ButtonRelease-1>", self.get_data)

    # ==================== HELPERS ====================
    def refresh_courses(self):
        try:
            with get_conn() as con:
                self.courses = {r["name"]: r["cid"] for r in
                                con.execute("SELECT cid, name FROM course ORDER BY name")}
        except sqlite3.Error as ex:
            self.courses = {}
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)

    def refresh_course_values(self):
        """Runs each time the drop-down opens, so new courses appear without reopening."""
        self.refresh_courses()
        self.txt_course["values"] = ["Select"] + sorted(self.courses)

    def set_address(self, text):
        self.txt_address.config(state=NORMAL)
        self.txt_address.delete("1.0", END)
        self.txt_address.insert(END, text)
        if not self.can_write:
            self.txt_address.config(state=DISABLED)

    def _error(self, message):
        messagebox.showerror("Error", message, parent=self.root)
        return None

    def read_form(self, adding):
        """Validated values for the INSERT/UPDATE, or None after showing an error."""
        roll = self.var_roll.get().strip()
        if not roll:
            return self._error("Roll No. should be required")
        if not (roll.isascii() and roll.isdigit() and int(roll) > 0):
            return self._error("Roll No. must be a positive number")
        name = self.var_name.get().strip()
        if not name:
            return self._error("Name should be required")
        email = self.var_email.get().strip()
        if email and not is_valid_email(email):
            return self._error("Enter a valid email address")
        contact = self.var_contact.get().strip()
        if contact and not is_valid_contact(contact):
            return self._error("Contact must be a 10-digit number")
        pin = self.var_pin.get().strip()
        if pin and not is_valid_pin(pin):
            return self._error("Pin Code must be 6 digits")
        dob = self.var_dob.get().strip()
        if dob:
            parsed = parse_date(dob)
            if parsed is None:
                return self._error("D.O.B must be a valid date in DD-MM-YYYY format")
            if parsed >= date.today():
                return self._error("D.O.B must be in the past")
            dob = format_date(parsed)
        admission = self.var_admission.get().strip() or format_date(date.today())
        parsed = parse_date(admission)
        if parsed is None:
            return self._error("Add. Date must be a valid date in DD-MM-YYYY format")
        admission = format_date(parsed)
        course = self.var_course.get()
        if course not in self.courses:
            return self._error("Please select a course")
        gender = self.var_gender.get()
        gender = "" if gender == "Select" else gender
        return dict(roll=int(roll), name=name, email=email, gender=gender, dob=dob,
                    contact=contact, admission=admission, course_id=self.courses[course],
                    state=self.var_state.get().strip(), city=self.var_city.get().strip(),
                    pin=pin, address=self.txt_address.get("1.0", END).strip())

    # ==================== DATABASE ACTIONS ====================
    def clear(self):
        self.selected_roll = None
        self.var_roll.set("")
        self.var_name.set("")
        self.var_email.set("")
        self.var_gender.set("Select")
        self.var_dob.set("")
        self.var_contact.set("")
        self.var_admission.set(format_date(date.today()))
        self.var_course.set("Select")
        self.var_state.set("")
        self.var_city.set("")
        self.var_pin.set("")
        self.set_address("")
        self.var_search.set("")
        if self.can_write:
            self.txt_roll.config(state="normal")
        self.show()

    def add(self):
        if not require_permission(self.user, "student.write", self.root, "add students"):
            return
        data = self.read_form(adding=True)
        if data is None:
            return
        try:
            with get_conn() as con:
                con.execute(
                    "INSERT INTO student (roll, name, email, gender, dob, contact, admission, "
                    "course_id, state, city, pin, address) VALUES (:roll, :name, :email, "
                    ":gender, :dob, :contact, :admission, :course_id, :state, :city, :pin, "
                    ":address)", data)
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Roll No. is already present, Try another",
                                 parent=self.root)
        except sqlite3.Error as ex:
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)
        else:
            messagebox.showinfo("Success", "Student has been added successfully",
                                parent=self.root)
            self.clear()

    def update(self):
        if not require_permission(self.user, "student.write", self.root, "update students"):
            return
        if self.selected_roll is None:
            messagebox.showerror("Error", "Select student from list", parent=self.root)
            return
        data = self.read_form(adding=False)
        if data is None:
            return
        data["roll"] = self.selected_roll
        try:
            with get_conn() as con:
                cur = con.execute(
                    "UPDATE student SET name=:name, email=:email, gender=:gender, dob=:dob, "
                    "contact=:contact, admission=:admission, course_id=:course_id, "
                    "state=:state, city=:city, pin=:pin, address=:address WHERE roll=:roll",
                    data)
                if cur.rowcount == 0:
                    messagebox.showerror("Error", "Select student from list", parent=self.root)
                    return
        except sqlite3.Error as ex:
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)
        else:
            messagebox.showinfo("Success", "Student has been updated successfully",
                                parent=self.root)
            self.clear()

    def delete(self):
        if not require_permission(self.user, "student.delete", self.root, "delete students"):
            return
        if self.selected_roll is None:
            messagebox.showerror("Error", "Select student from list", parent=self.root)
            return
        try:
            with get_conn() as con:
                count = con.execute("SELECT COUNT(*) FROM result WHERE roll=?",
                                    (self.selected_roll,)).fetchone()[0]
        except sqlite3.Error as ex:
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)
            return
        warning = (f"\n\nThis will also delete {count} result"
                   f"{'s' if count != 1 else ''} of this student." if count else "")
        if not messagebox.askyesno("Confirm",
                                   f"Do you want to delete this student?{warning}",
                                   parent=self.root):
            return
        try:
            with get_conn() as con:
                con.execute("DELETE FROM student WHERE roll=?", (self.selected_roll,))
        except sqlite3.Error as ex:
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)
        else:
            messagebox.showinfo("Delete", "Student has been deleted successfully",
                                parent=self.root)
            self.clear()

    def get_data(self, ev):
        row = self.rows.get(self.StudentTable.focus())
        if not row:
            return                          # clicked on empty space / header
        self.selected_roll = row[0]
        if self.can_write:
            self.txt_roll.config(state="normal")
        self.var_roll.set(row[0])
        if self.can_write:
            self.txt_roll.config(state="readonly")   # roll is the key, keep it fixed
        self.var_name.set(row[1])
        self.var_email.set(row[2] or "")
        self.var_gender.set(row[3] or "Select")
        self.var_dob.set(row[4] or "")
        self.var_contact.set(row[5] or "")
        self.var_admission.set(row[6] or "")
        self.var_course.set(row[7] or "Select")
        self.var_state.set(row[8] or "")
        self.var_city.set(row[9] or "")
        self.var_pin.set(row[10] or "")
        self.set_address(row[11] or "")

    def fill_table(self, rows):
        self.StudentTable.delete(*self.StudentTable.get_children())
        self.rows.clear()
        for i, r in enumerate(rows):
            row = tuple(r)
            iid = self.StudentTable.insert("", END, values=row,
                                           tags=("even" if i % 2 == 0 else "odd",))
            self.rows[iid] = row            # keeps real types (no '007' -> 7 surprises)
        n = len(rows)
        self.lbl_count.config(text=f"{n} record{'s' if n != 1 else ''}")

    def show(self):
        try:
            with get_conn() as con:
                rows = con.execute(STUDENT_SELECT + " ORDER BY s.roll").fetchall()
            self.fill_table(rows)
        except sqlite3.Error as ex:
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)

    def search(self):
        keyword = self.var_search.get().strip()
        if not keyword:
            messagebox.showerror("Error", "Search input should be required", parent=self.root)
            return
        pattern = like_pattern(keyword)
        try:
            with get_conn() as con:
                rows = con.execute(
                    STUDENT_SELECT + " WHERE CAST(s.roll AS TEXT) LIKE ? ESCAPE '\\' "
                    "OR s.name LIKE ? ESCAPE '\\' ORDER BY s.roll",
                    (pattern, pattern)).fetchall()
        except sqlite3.Error as ex:
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)
            return
        if rows:
            self.fill_table(rows)
        else:
            messagebox.showerror("Error", "No record found", parent=self.root)
