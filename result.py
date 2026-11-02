from tkinter import *
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import sqlite3

import config
from db import get_conn
from theme import (ACCENT, BLUE, BLUE_HOVER, CARD_BG, FONT, GREEN, GREEN_HOVER, GREY,
                   GREY_HOVER, MUTED, NAVY, PAGE_BG, apply_theme)
from validators import parse_number
from widgets import (card_title, make_button, make_card, make_entry, make_label,
                     page_header, require_permission)


class ResultClass:
    def __init__(self, root, user):
        self.root = root
        self.user = user
        self.course_id = None

        self.root.title("Student Result Management System")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.minsize(1000, 600)
        self.root.config(bg=PAGE_BG)
        self.root.focus_force()

        apply_theme(self.root)
        self.var_roll = StringVar(value="Select")
        self.var_name = StringVar()
        self.var_course = StringVar()
        self.var_marks = StringVar()
        self.var_full_marks = StringVar()
        self.var_percent = StringVar(value="--")
        self.roll_list = self.fetch_rolls()

        # live percentage preview
        self.var_marks.trace_add("write", lambda *a: self.update_preview())
        self.var_full_marks.trace_add("write", lambda *a: self.update_preview())

        page_header(self.root, "📝  ADD STUDENT RESULT DETAILS",
                    "Select  •  Enter Marks  •  Submit")
        self.build_body()

    # ==================== BODY ====================
    def build_body(self):
        body = Frame(self.root, bg=PAGE_BG)
        body.pack(side=TOP, fill=BOTH, expand=True, padx=15, pady=15)
        body.columnconfigure(0, weight=2, uniform="cols")
        body.columnconfigure(1, weight=3, uniform="cols")
        body.rowconfigure(0, weight=1)
        self.build_form(body)
        self.build_side(body)

    def build_form(self, parent):
        card = make_card(parent)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        card_title(card, "Result Entry").pack(anchor="w", padx=18, pady=(16, 10))

        form = Frame(card, bg=CARD_BG)
        form.pack(fill=X, padx=18)
        form.columnconfigure(1, weight=1)

        def pair(row, label, widget, **grid):
            make_label(form, label).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=12)
            widget.grid(row=row, column=1, sticky="ew", pady=8, **grid)

        picker = Frame(form, bg=CARD_BG)
        picker.columnconfigure(0, weight=1)
        self.txt_student = ttk.Combobox(picker, textvariable=self.var_roll,
                                        values=self.roll_list, state="readonly",
                                        postcommand=self.refresh_rolls, font=(FONT, 13),
                                        style="Srms.TCombobox")
        self.txt_student.grid(row=0, column=0, sticky="ew")
        self.txt_student.bind("<<ComboboxSelected>>", lambda e: self.search())
        make_button(picker, "Search", self.search, BLUE, BLUE_HOVER
                    ).grid(row=0, column=1, padx=(10, 0), ipadx=14)
        pair(0, "Select Student", picker)

        pair(1, "Name", make_entry(form, self.var_name, readonly=True, size=13), ipady=5)
        pair(2, "Course", make_entry(form, self.var_course, readonly=True, size=13), ipady=5)
        pair(3, "Marks Obtained", make_entry(form, self.var_marks, size=13), ipady=5)
        pair(4, "Full Marks", make_entry(form, self.var_full_marks, size=13), ipady=5)

        btns = Frame(card, bg=CARD_BG)
        btns.pack(fill=X, padx=18, pady=(14, 18))
        btns.columnconfigure(0, weight=1, uniform="btn")
        btns.columnconfigure(1, weight=1, uniform="btn")
        make_button(btns, "✔  Submit", self.add, GREEN, GREEN_HOVER
                    ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        make_button(btns, "🧹  Clear", self.clear, GREY, GREY_HOVER
                    ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def build_side(self, parent):
        side = Frame(parent, bg=PAGE_BG)
        side.grid(row=0, column=1, sticky="nsew")
        side.columnconfigure(0, weight=1)
        side.rowconfigure(0, weight=1)

        img_frame = Frame(side, bg=BLUE)
        img_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 14))
        self.bg_label = Label(img_frame, bg=BLUE, bd=0)
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        try:
            self.bg_src = Image.open(config.image_path("result.jpg"))
        except Exception:
            self.bg_src = None              # the picture is optional
        img_frame.bind("<Configure>", self.on_image_resize)
        Label(img_frame, text="Enter marks carefully before submitting",
              font=(FONT, 15, "bold"), bg=NAVY, fg="white", pady=10
              ).place(relx=0, rely=1, relwidth=1, anchor="sw")

        prev = make_card(side)
        prev.grid(row=1, column=0, sticky="ew")
        Frame(prev, bg=ACCENT, width=8).pack(side=LEFT, fill=Y)
        Label(prev, text="📊", font=(FONT, 34), bg=CARD_BG, fg=ACCENT
              ).pack(side=LEFT, padx=16, pady=14)
        info = Frame(prev, bg=CARD_BG)
        info.pack(side=LEFT, pady=10)
        Label(info, textvariable=self.var_percent, font=(FONT, 32, "bold"),
              bg=CARD_BG, fg=ACCENT).pack(anchor="w")
        Label(info, text="Percentage (live preview)", font=(FONT, 13),
              bg=CARD_BG, fg=MUTED).pack(anchor="w")

    def on_image_resize(self, event):
        if self.bg_src is None or event.width < 10 or event.height < 10:
            return
        img = self.bg_src.resize((event.width, event.height), Image.Resampling.LANCZOS)
        self.bg_img = ImageTk.PhotoImage(img)
        self.bg_label.config(image=self.bg_img)

    def update_preview(self):
        marks = parse_number(self.var_marks.get())
        full = parse_number(self.var_full_marks.get())
        if marks is None or full is None or full <= 0:
            self.var_percent.set("--")
        else:
            self.var_percent.set(f"{marks / full * 100:.2f}%")

    # ==================== DATABASE ACTIONS ====================
    def fetch_rolls(self):
        try:
            with get_conn() as con:
                return [str(r["roll"]) for r in
                        con.execute("SELECT roll FROM student ORDER BY roll")]
        except sqlite3.Error as ex:
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)
            return []

    def refresh_rolls(self):
        """Runs each time the drop-down opens, so newly added students appear."""
        self.roll_list = self.fetch_rolls()
        self.txt_student["values"] = self.roll_list

    def search(self):
        roll = self.var_roll.get()
        if not roll.isdigit():
            messagebox.showerror("Error", "Please select a student first", parent=self.root)
            return
        try:
            with get_conn() as con:
                row = con.execute(
                    "SELECT s.name, s.course_id, c.name AS course FROM student s "
                    "LEFT JOIN course c ON c.cid = s.course_id WHERE s.roll = ?",
                    (int(roll),)).fetchone()
        except sqlite3.Error as ex:
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)
            return
        if row is None:
            messagebox.showerror("Error", "No record found", parent=self.root)
        elif row["course_id"] is None:
            self.var_name.set(row["name"])
            self.var_course.set("")
            self.course_id = None
            messagebox.showerror("Error", "This student has no course. Assign one in the "
                                 "Student screen first.", parent=self.root)
        else:
            self.var_name.set(row["name"])
            self.var_course.set(row["course"])
            self.course_id = row["course_id"]

    def add(self):
        if not require_permission(self.user, "result.write", self.root, "add results"):
            return
        if self.course_id is None:
            messagebox.showerror("Error", "Please first search student record",
                                 parent=self.root)
            return
        marks = parse_number(self.var_marks.get())
        full = parse_number(self.var_full_marks.get())
        if marks is None or full is None:
            messagebox.showerror("Error", "Marks and Full Marks must be numbers",
                                 parent=self.root)
            return
        if full <= 0:
            messagebox.showerror("Error", "Full Marks must be greater than 0",
                                 parent=self.root)
            return
        if marks < 0 or marks > full:
            messagebox.showerror("Error", "Marks Obtained must be between 0 and Full Marks",
                                 parent=self.root)
            return
        try:
            with get_conn() as con:
                con.execute("INSERT INTO result (roll, course_id, marks_ob, full_marks) "
                            "VALUES (?, ?, ?, ?)",
                            (int(self.var_roll.get()), self.course_id, marks, full))
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Result already present, Try another",
                                 parent=self.root)
        except sqlite3.Error as ex:
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)
        else:
            messagebox.showinfo("Success", "Result has been added successfully",
                                parent=self.root)
            self.clear()

    def clear(self):
        self.course_id = None
        self.var_roll.set("Select")
        self.var_name.set("")
        self.var_course.set("")
        self.var_marks.set("")
        self.var_full_marks.set("")
        self.var_percent.set("--")
