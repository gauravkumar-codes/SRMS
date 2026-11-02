from tkinter import *
from tkinter import ttk, messagebox
import sqlite3

import auth
from db import get_conn
from theme import (BLUE, BLUE_HOVER, CARD_BG, FIELD_BG, FONT, GREEN, GREEN_HOVER, GREY,
                   GREY_HOVER, MUTED, NAVY, PAGE_BG, RED, RED_HOVER, STRIPE, BORDER,
                   apply_theme)
from validators import fmt_num, like_pattern, parse_number
from widgets import (card_title, make_button, make_card, make_entry, make_label,
                     page_header, require_permission)


class CourseClass:
    def __init__(self, root, user):
        self.root = root
        self.user = user
        self.can_write = auth.can(user, "course.write")
        self.selected_cid = None
        self.rows = {}                      # tree item id -> full db row

        self.root.title("Student Result Management System")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.minsize(1000, 600)
        self.root.config(bg=PAGE_BG)
        self.root.focus_force()

        apply_theme(self.root)
        self.var_coursename = StringVar()
        self.var_duration = StringVar()
        self.var_fee = StringVar()
        self.var_search = StringVar()

        page_header(self.root, "📚  MANAGE COURSE DETAILS",
                    "Add  •  Update  •  Delete  •  Search" if self.can_write
                    else "View only")
        self.build_body()
        self.show()

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
        card_title(card, "Course Information").pack(anchor="w", padx=18, pady=(16, 10))

        form = Frame(card, bg=CARD_BG)
        form.pack(fill=BOTH, expand=True, padx=18)
        form.columnconfigure(1, weight=1)
        readonly = not self.can_write

        def pair(row, label, widget, sticky="ew"):
            make_label(form, label).grid(row=row, column=0, sticky="nw", padx=(0, 14), pady=12)
            widget.grid(row=row, column=1, sticky=sticky, pady=8)

        self.txt_coursename = make_entry(form, self.var_coursename, readonly=readonly)
        pair(0, "Course Name", self.txt_coursename)
        self.txt_coursename.grid_configure(ipady=5)
        txt_duration = make_entry(form, self.var_duration, readonly=readonly)
        pair(1, "Duration", txt_duration)
        txt_duration.grid_configure(ipady=5)
        txt_fee = make_entry(form, self.var_fee, readonly=readonly)
        pair(2, "Course Fee", txt_fee)
        txt_fee.grid_configure(ipady=5)

        self.txt_description = Text(form, font=(FONT, 12), bg=FIELD_BG, fg=NAVY, height=8,
                                    relief=FLAT, highlightthickness=1,
                                    highlightbackground=BORDER, highlightcolor=BLUE,
                                    insertbackground=NAVY, insertwidth=2, wrap=WORD,
                                    state=DISABLED if readonly else NORMAL)
        pair(3, "Description", self.txt_description, sticky="nsew")
        form.rowconfigure(3, weight=1)

        btns = Frame(card, bg=CARD_BG)
        btns.pack(fill=X, padx=18, pady=(8, 18))
        if not self.can_write:
            Label(btns, text="👁  View only — your role cannot modify courses",
                  font=(FONT, 12), bg=CARD_BG, fg=MUTED).pack(anchor="w")
            return
        specs = [("💾  Save", self.add, GREEN, GREEN_HOVER),
                 ("✏️  Update", self.update, BLUE, BLUE_HOVER),
                 ("🗑  Delete", self.delete, RED, RED_HOVER),
                 ("🧹  Clear", self.clear, GREY, GREY_HOVER)]
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
        card_title(top, "Course List").pack(side=LEFT)
        self.lbl_count = Label(top, text="0 courses", font=(FONT, 11), bg=CARD_BG, fg=MUTED)
        self.lbl_count.pack(side=RIGHT)

        search = Frame(card, bg=PAGE_BG)
        search.pack(fill=X, padx=18, pady=(0, 10))
        Label(search, text="🔍  Course Name", font=(FONT, 12, "bold"), bg=PAGE_BG,
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
        self.CourseTable = ttk.Treeview(
            wrap, columns=("cid", "course", "duration", "fee", "description"),
            show="headings", style="Srms.Treeview",
            xscrollcommand=scrollx.set, yscrollcommand=scrolly.set)
        scrolly.config(command=self.CourseTable.yview)
        scrollx.config(command=self.CourseTable.xview)
        scrolly.pack(side=RIGHT, fill=Y)
        scrollx.pack(side=BOTTOM, fill=X)
        self.CourseTable.pack(fill=BOTH, expand=True)

        headings = {"cid": ("Course ID", 90), "course": ("Course Name", 180),
                    "duration": ("Duration", 130), "fee": ("Course Fee", 130),
                    "description": ("Description", 320)}
        for key, (text, width) in headings.items():
            self.CourseTable.heading(key, text=text)
            self.CourseTable.column(key, width=width, minwidth=70, anchor="w")
        self.CourseTable.tag_configure("odd", background=STRIPE)
        self.CourseTable.tag_configure("even", background="white")
        self.CourseTable.bind("<ButtonRelease-1>", self.get_data)

    # ==================== HELPERS ====================
    def set_description(self, text):
        self.txt_description.config(state=NORMAL)
        self.txt_description.delete("1.0", END)
        self.txt_description.insert(END, text)
        if not self.can_write:
            self.txt_description.config(state=DISABLED)

    def read_form(self):
        """Validated (name, duration, fee, description), or None after showing an error."""
        name = self.var_coursename.get().strip()
        if not name:
            messagebox.showerror("Error", "Course Name should be required", parent=self.root)
            return None
        fee = parse_number(self.var_fee.get())
        if fee is None or fee < 0:
            messagebox.showerror("Error", "Course Fee must be a number (0 or more)",
                                 parent=self.root)
            return None
        return (name, self.var_duration.get().strip(), fee,
                self.txt_description.get("1.0", END).strip())

    # ==================== DATABASE ACTIONS ====================
    def clear(self):
        self.selected_cid = None
        self.var_coursename.set("")
        self.var_duration.set("")
        self.var_fee.set("")
        self.var_search.set("")
        self.set_description("")
        self.show()

    def add(self):
        if not require_permission(self.user, "course.write", self.root, "add courses"):
            return
        data = self.read_form()
        if data is None:
            return
        try:
            with get_conn() as con:
                con.execute("INSERT INTO course (name, duration, charges, description) "
                            "VALUES (?, ?, ?, ?)", data)
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "This Course is already present, try another",
                                 parent=self.root)
        except sqlite3.Error as ex:
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)
        else:
            messagebox.showinfo("Success", "Course has been added successfully",
                                parent=self.root)
            self.clear()

    def update(self):
        if not require_permission(self.user, "course.write", self.root, "update courses"):
            return
        if self.selected_cid is None:
            messagebox.showerror("Error", "Select Course from list", parent=self.root)
            return
        data = self.read_form()
        if data is None:
            return
        try:
            with get_conn() as con:
                con.execute("UPDATE course SET name=?, duration=?, charges=?, description=? "
                            "WHERE cid=?", data + (self.selected_cid,))
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Another course already has this name",
                                 parent=self.root)
        except sqlite3.Error as ex:
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)
        else:
            messagebox.showinfo("Success", "Course has been updated successfully",
                                parent=self.root)
            self.clear()

    def delete(self):
        if not require_permission(self.user, "course.write", self.root, "delete courses"):
            return
        if self.selected_cid is None:
            messagebox.showerror("Error", "Select Course from list", parent=self.root)
            return
        if not messagebox.askyesno("Confirm", "Do you want to delete this course?",
                                   parent=self.root):
            return
        try:
            with get_conn() as con:
                con.execute("DELETE FROM course WHERE cid=?", (self.selected_cid,))
        except sqlite3.IntegrityError:
            messagebox.showerror(
                "Cannot Delete",
                "This course is still used by students or results.\n"
                "Move or delete those records first.", parent=self.root)
        except sqlite3.Error as ex:
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)
        else:
            messagebox.showinfo("Delete", "Course has been deleted successfully",
                                parent=self.root)
            self.clear()

    def get_data(self, ev):
        row = self.rows.get(self.CourseTable.focus())
        if not row:
            return                          # clicked on empty space / header
        cid, name, duration, charges, description = row
        self.selected_cid = cid
        self.var_coursename.set(name)
        self.var_duration.set(duration or "")
        self.var_fee.set(fmt_num(charges))
        self.set_description(description or "")

    def fill_table(self, rows):
        self.CourseTable.delete(*self.CourseTable.get_children())
        self.rows.clear()
        for i, r in enumerate(rows):
            row = tuple(r)
            iid = self.CourseTable.insert(
                "", END, values=(row[0], row[1], row[2], fmt_num(row[3]), row[4]),
                tags=("even" if i % 2 == 0 else "odd",))
            self.rows[iid] = row
        n = len(rows)
        self.lbl_count.config(text=f"{n} course{'s' if n != 1 else ''}")

    def show(self):
        try:
            with get_conn() as con:
                rows = con.execute("SELECT cid, name, duration, charges, description "
                                   "FROM course ORDER BY name").fetchall()
            self.fill_table(rows)
        except sqlite3.Error as ex:
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)

    def search(self):
        keyword = self.var_search.get().strip()
        if not keyword:
            self.show()
            return
        try:
            with get_conn() as con:
                rows = con.execute(
                    "SELECT cid, name, duration, charges, description FROM course "
                    "WHERE name LIKE ? ESCAPE '\\' ORDER BY name",
                    (like_pattern(keyword),)).fetchall()
        except sqlite3.Error as ex:
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)
            return
        if rows:
            self.fill_table(rows)
        else:
            messagebox.showerror("Error", "No record found", parent=self.root)
