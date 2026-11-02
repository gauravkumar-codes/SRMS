from tkinter import *
from tkinter import ttk, messagebox
import sqlite3

import auth
from db import get_conn
from theme import (ACCENT, BLUE, BLUE_HOVER, CARD_BG, FONT, GREEN, GREY, GREY_HOVER,
                   LIGHT_BLUE, MUTED, NAVY, PAGE_BG, RED, RED_HOVER, STRIPE, apply_theme)
from validators import fmt_num
from widgets import (card_title, make_button, make_card, make_entry, page_header,
                     require_permission)

EMPTY = "—"

# percentage is computed here, never stored
RESULT_SELECT = (
    "SELECT r.rid, s.roll, s.name, c.name, r.marks_ob, r.full_marks, "
    "r.marks_ob * 100.0 / r.full_marks "
    "FROM result r JOIN student s ON s.roll = r.roll JOIN course c ON c.cid = r.course_id")


class ReportClass:
    def __init__(self, root, user):
        self.root = root
        self.user = user
        self.can_delete = auth.can(user, "result.delete")
        self.rows = {}                      # tree item id -> result row
        self.var_id = None                  # rid of the result shown in the tiles

        self.root.title("Student Result Management System")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.minsize(1000, 650)
        self.root.config(bg=PAGE_BG)
        self.root.focus_force()

        apply_theme(self.root)
        self.var_search = StringVar()

        page_header(self.root, "📊  VIEW STUDENT RESULT",
                    "Search  •  View  •  Delete" if self.can_delete else "Search  •  View")
        self.build_body()

    # ==================== BODY ====================
    def build_body(self):
        body = Frame(self.root, bg=PAGE_BG)
        body.pack(side=TOP, fill=BOTH, expand=True, padx=15, pady=15)
        body.columnconfigure(0, weight=1, uniform="gut")
        body.columnconfigure(1, weight=6)
        body.columnconfigure(2, weight=1, uniform="gut")
        body.rowconfigure(0, weight=1)

        content = Frame(body, bg=PAGE_BG)
        content.grid(row=0, column=1, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)
        self.build_search(content)
        self.build_result(content)

    def build_search(self, parent):
        card = make_card(parent)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        card_title(card, "Find a Result").pack(anchor="w", padx=18, pady=(16, 10))

        bar = Frame(card, bg=PAGE_BG)
        bar.pack(fill=X, padx=18, pady=(0, 18))
        Label(bar, text="🔍  Roll No.", font=(FONT, 12, "bold"), bg=PAGE_BG, fg=NAVY
              ).pack(side=LEFT, padx=(10, 10), pady=10)
        txt_search = make_entry(bar, self.var_search, size=13)
        txt_search.pack(side=LEFT, fill=X, expand=True, ipady=5, pady=10)
        txt_search.bind("<Return>", lambda e: self.search())
        txt_search.focus_set()
        make_button(bar, "Search", self.search, BLUE, BLUE_HOVER
                    ).pack(side=LEFT, padx=(10, 6), pady=10, ipadx=16)
        make_button(bar, "Clear", self.clear, GREY, GREY_HOVER
                    ).pack(side=LEFT, padx=(0, 10), pady=10, ipadx=16)

    def make_tile(self, parent, row, col, caption, color, size=20):
        """Info tile in the style of the dashboard stat cards; returns the value Label."""
        tile = make_card(parent)
        tile.grid(row=row, column=col, sticky="nsew", padx=7, pady=7)
        Frame(tile, bg=color, width=8).pack(side=LEFT, fill=Y)
        inner = Frame(tile, bg=CARD_BG)
        inner.pack(side=LEFT, fill=BOTH, expand=True, padx=16, pady=10)
        Label(inner, text=caption, font=(FONT, 12), bg=CARD_BG, fg=MUTED).pack(anchor="w")
        value = Label(inner, text=EMPTY, font=(FONT, size, "bold"), bg=CARD_BG, fg=color,
                      wraplength=260, justify=LEFT)
        value.pack(anchor="w", pady=(4, 0))
        return value

    def build_result(self, parent):
        card = make_card(parent)
        card.grid(row=1, column=0, sticky="nsew")

        top = Frame(card, bg=CARD_BG)
        top.pack(fill=X, padx=18, pady=(16, 6))
        card_title(top, "Student Result").pack(side=LEFT)
        self.lbl_hint = Label(top, text="Search a roll number to view the result",
                              font=(FONT, 11), bg=CARD_BG, fg=MUTED)
        self.lbl_hint.pack(side=RIGHT)

        grid = Frame(card, bg=CARD_BG)
        grid.pack(fill=BOTH, expand=True, padx=11, pady=(4, 6))
        for c in range(3):
            grid.columnconfigure(c, weight=1, uniform="tile")
        for r in range(2):
            grid.rowconfigure(r, weight=1, uniform="trow")
        self.roll = self.make_tile(grid, 0, 0, "Roll No.", BLUE)
        self.name = self.make_tile(grid, 0, 1, "Student Name", BLUE)
        self.course = self.make_tile(grid, 0, 2, "Course", BLUE)
        self.marks = self.make_tile(grid, 1, 0, "Marks Obtained", LIGHT_BLUE, size=26)
        self.full = self.make_tile(grid, 1, 1, "Total Marks", GREEN, size=26)
        self.per = self.make_tile(grid, 1, 2, "Percentage", ACCENT, size=26)

        # every result of the searched student (one row per course)
        table_wrap = Frame(card, bg=CARD_BG)
        table_wrap.pack(fill=X, padx=18, pady=(4, 6))
        self.ResultTable = ttk.Treeview(
            table_wrap, columns=("course", "marks", "full", "per"), show="headings",
            height=4, style="Srms.Treeview")
        for key, text, width in (("course", "Course", 220), ("marks", "Marks Obtained", 140),
                                 ("full", "Total Marks", 140), ("per", "Percentage", 120)):
            self.ResultTable.heading(key, text=text)
            self.ResultTable.column(key, width=width, anchor="w")
        self.ResultTable.pack(fill=X)
        self.ResultTable.tag_configure("odd", background=STRIPE)
        self.ResultTable.tag_configure("even", background="white")
        self.ResultTable.bind("<<TreeviewSelect>>", self.on_select)

        if self.can_delete:
            btns = Frame(card, bg=CARD_BG)
            btns.pack(fill=X, padx=18, pady=(6, 18))
            make_button(btns, "🗑  Delete Result", self.delete, RED, RED_HOVER
                        ).pack(side=RIGHT, ipadx=18)
        else:
            Frame(card, bg=CARD_BG, height=14).pack()

    # ==================== ACTIONS ====================
    def show_result(self, row):
        """row = (rid, roll, name, course, marks_ob, full_marks, percentage)"""
        self.var_id = row[0]
        self.roll.config(text=str(row[1]))
        self.name.config(text=row[2])
        self.course.config(text=row[3])
        self.marks.config(text=fmt_num(row[4]))
        self.full.config(text=fmt_num(row[5]))
        self.per.config(text=f"{row[6]:.2f}%")

    def reset_tiles(self):
        self.var_id = None
        for lbl in (self.roll, self.name, self.course, self.marks, self.full, self.per):
            lbl.config(text=EMPTY)

    def fill_table(self, rows):
        self.ResultTable.delete(*self.ResultTable.get_children())
        self.rows.clear()
        first = None
        for i, r in enumerate(rows):
            row = tuple(r)
            iid = self.ResultTable.insert(
                "", END, values=(row[3], fmt_num(row[4]), fmt_num(row[5]), f"{row[6]:.2f}%"),
                tags=("even" if i % 2 == 0 else "odd",))
            self.rows[iid] = row
            first = first or iid
        if first:
            self.ResultTable.selection_set(first)   # triggers on_select -> tiles

    def on_select(self, event=None):
        selection = self.ResultTable.selection()
        row = self.rows.get(selection[0]) if selection else None
        if row:
            self.show_result(row)

    def search(self):
        roll = self.var_search.get().strip()
        if not roll:
            messagebox.showerror("Error", "Roll No. should be required", parent=self.root)
            return
        if not (roll.isascii() and roll.isdigit()):
            messagebox.showerror("Error", "Roll No. must be a number", parent=self.root)
            return
        try:
            with get_conn() as con:
                rows = con.execute(RESULT_SELECT + " WHERE r.roll = ? ORDER BY c.name",
                                   (int(roll),)).fetchall()
        except sqlite3.Error as ex:
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)
            return
        if not rows:
            messagebox.showerror("Error", "No record found", parent=self.root)
            return
        self.fill_table(rows)
        n = len(rows)
        self.lbl_hint.config(text=f"{n} result{'s' if n != 1 else ''} found")

    def clear(self):
        self.var_search.set("")
        self.ResultTable.delete(*self.ResultTable.get_children())
        self.rows.clear()
        self.reset_tiles()
        self.lbl_hint.config(text="Search a roll number to view the result")

    def delete(self):
        if not require_permission(self.user, "result.delete", self.root, "delete results"):
            return
        if self.var_id is None:
            messagebox.showerror("Error", "Search student result first", parent=self.root)
            return
        if not messagebox.askyesno("Confirm", "Do you want to delete this result?",
                                   parent=self.root):
            return
        try:
            with get_conn() as con:
                cur = con.execute("DELETE FROM result WHERE rid = ?", (self.var_id,))
        except sqlite3.Error as ex:
            messagebox.showerror("Error", f"Error due to {ex}", parent=self.root)
            return
        if cur.rowcount == 0:
            messagebox.showerror("Error", "Invalid Student Result", parent=self.root)
            return
        messagebox.showinfo("Delete", "Result has been deleted successfully", parent=self.root)
        # re-run the search so the list shows what is left for this student
        remaining = self.var_search.get().strip()
        self.clear()
        if remaining.isdigit():
            self.var_search.set(remaining)
            try:
                with get_conn() as con:
                    rows = con.execute(RESULT_SELECT + " WHERE r.roll = ? ORDER BY c.name",
                                       (int(remaining),)).fetchall()
            except sqlite3.Error:
                rows = []
            if rows:
                self.fill_table(rows)
                self.lbl_hint.config(text=f"{len(rows)} result(s) found")
