from tkinter import *
from PIL import Image, ImageTk
from tkinter import messagebox
import math
import sqlite3
from datetime import datetime

import auth
import config
from course import CourseClass
from db import get_conn
from report import ReportClass
from result import ResultClass
from student import StudentClass
from theme import (ACCENT, BLUE, BLUE_HOVER, CARD_BG, BORDER, FONT, GREEN, GREY, GREY_HOVER,
                   LIGHT_BLUE, LIGHT_TEXT, MUTED, NAVY, PAGE_BG, RED, RED_HOVER)
from users import UserAdminClass


class RMS:
    def __init__(self, root, user):
        self.root = root
        self.user = user
        self.next_screen = (None, None)      # read by main.py after the window closes
        self.windows = {}                    # module key -> (Toplevel, object)
        self.btn_users = None

        self.root.title("Student Result Management System")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.minsize(1000, 650)
        self.root.config(bg=PAGE_BG)

        # clock geometry (filled in when the canvas is drawn)
        self.cx = self.cy = self.r = 0

        self.build_header()
        self.build_menu()
        self.build_footer()
        self.build_body()

        self.update_clock()
        self.update_counts()

    # ==================== HEADER ====================
    def build_header(self):
        header = Frame(self.root, bg=NAVY, height=70)
        header.pack(side=TOP, fill=X)
        header.pack_propagate(False)

        try:
            logo = Image.open(config.image_path("logo_p.jpg")).resize(
                (46, 46), Image.Resampling.LANCZOS)
            self.logo_dash = ImageTk.PhotoImage(logo)
            Label(header, image=self.logo_dash, bg=NAVY).pack(side=LEFT, padx=(20, 10))
        except Exception:
            pass  # logo is optional

        Label(header, text="STUDENT RESULT MANAGEMENT SYSTEM", font=(FONT, 24, "bold"),
              bg=NAVY, fg="white").pack(side=LEFT)

        hour = datetime.now().hour
        greet = "Good Morning" if hour < 12 else "Good Afternoon" if hour < 18 else "Good Evening"
        Label(header, text=f"{greet}, {self.user.first_name}  ({self.user.role_label})",
              font=(FONT, 15), bg=NAVY, fg=LIGHT_TEXT).pack(side=RIGHT, padx=25)

        Frame(self.root, bg=ACCENT, height=3).pack(side=TOP, fill=X)

    # ==================== MENU ====================
    def make_nav_button(self, parent, text, command, bg=BLUE, hover=BLUE_HOVER):
        lbl = Label(parent, text=text, font=(FONT, 15, "bold"), bg=bg, fg="white",
                    cursor="hand2", padx=26, pady=10)
        lbl.bind("<Button-1>", lambda e: command())
        lbl.bind("<Enter>", lambda e: lbl.config(bg=hover))
        lbl.bind("<Leave>", lambda e: lbl.config(bg=bg))
        return lbl

    def build_menu(self):
        menu = Frame(self.root, bg=PAGE_BG)
        menu.pack(side=TOP, fill=X, padx=15, pady=(12, 6))

        # (permission needed to SEE the button, text, key, window class)
        items = [("course.read", "📚  Course", "course", CourseClass),
                 ("student.read", "🎓  Student", "student", StudentClass),
                 ("result.write", "📝  Result", "result", ResultClass),
                 ("result.read", "📊  View Results", "report", ReportClass),
                 ("users.manage", "👥  Users", "users", UserAdminClass)]
        for permission, text, key, cls in items:
            if not auth.can(self.user, permission):
                continue                      # the button is hidden, not just disabled
            btn = self.make_nav_button(menu, text, lambda k=key, c=cls: self.open_module(k, c))
            btn.pack(side=LEFT, padx=(0, 10))
            if key == "users":
                self.btn_users = btn

        self.make_nav_button(menu, "⏻  Exit", self.exit_app, bg=RED, hover=RED_HOVER
                             ).pack(side=RIGHT)
        self.make_nav_button(menu, "↩  Log out", self.logout, bg=GREY, hover=GREY_HOVER
                             ).pack(side=RIGHT, padx=(0, 10))

    # ==================== FOOTER ====================
    def build_footer(self):
        Label(self.root,
              text="SRMS - Student Result Management System\n"
                   "Contact Us for any Technical Issue: 987xxxxx01",
              font=(FONT, 11), bg=NAVY, fg="white", pady=6).pack(side=BOTTOM, fill=X)

    # ==================== BODY ====================
    def build_body(self):
        body = Frame(self.root, bg=PAGE_BG)
        body.pack(side=TOP, fill=BOTH, expand=True, padx=15, pady=(4, 12))
        body.columnconfigure(0, weight=2, uniform="cols")
        body.columnconfigure(1, weight=3, uniform="cols")
        body.rowconfigure(0, weight=1)
        body.rowconfigure(1, weight=0)

        clock_card = Frame(body, bg=NAVY)
        clock_card.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 14))
        Label(clock_card, text="LIVE CLOCK", font=(FONT, 13, "bold"), bg=NAVY, fg=LIGHT_TEXT
              ).pack(pady=(14, 0))
        self.clock_canvas = Canvas(clock_card, bg=NAVY, highlightthickness=0, bd=0)
        self.clock_canvas.pack(fill=BOTH, expand=True)
        self.clock_canvas.bind("<Configure>", self.on_clock_resize)

        img_frame = Frame(body, bg=BLUE)
        img_frame.grid(row=0, column=1, sticky="nsew", pady=(0, 14))
        self.bg_label = Label(img_frame, bg=BLUE, bd=0)
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        try:
            self.bg_src = Image.open(config.image_path("bg_img.jpg"))
        except Exception:
            self.bg_src = None
        img_frame.bind("<Configure>", self.on_image_resize)
        Label(img_frame, text="Welcome to the Student Result Management System",
              font=(FONT, 16, "bold"), bg=NAVY, fg="white", pady=10
              ).place(relx=0, rely=1, relwidth=1, anchor="sw")

        stats = Frame(body, bg=PAGE_BG)
        stats.grid(row=1, column=1, sticky="ew")
        for i in range(3):
            stats.columnconfigure(i, weight=1, uniform="stat")
        self.lbl_course = self.make_stat_card(stats, 0, "Total Courses", "📚", ACCENT)
        self.lbl_student = self.make_stat_card(stats, 1, "Total Students", "🎓", LIGHT_BLUE)
        self.lbl_result = self.make_stat_card(stats, 2, "Total Results", "📝", GREEN)

    def make_stat_card(self, parent, col, title, icon, color):
        card = Frame(parent, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        card.grid(row=0, column=col, sticky="ew",
                  padx=(0 if col == 0 else 7, 0 if col == 2 else 7))
        Frame(card, bg=color, width=8).pack(side=LEFT, fill=Y)
        Label(card, text=icon, font=(FONT, 34), bg=CARD_BG, fg=color
              ).pack(side=LEFT, padx=16, pady=14)
        info = Frame(card, bg=CARD_BG)
        info.pack(side=LEFT, pady=10)
        value = Label(info, text="0", font=(FONT, 32, "bold"), bg=CARD_BG, fg=color)
        value.pack(anchor="w")
        Label(info, text=title, font=(FONT, 13), bg=CARD_BG, fg=MUTED).pack(anchor="w")
        return value

    # ==================== IMAGE RESIZE ====================
    def on_image_resize(self, event):
        if self.bg_src is None or event.width < 10 or event.height < 10:
            return
        img = self.bg_src.resize((event.width, event.height), Image.Resampling.LANCZOS)
        self.bg_img = ImageTk.PhotoImage(img)
        self.bg_label.config(image=self.bg_img)

    # ==================== ANALOG CLOCK ====================
    def on_clock_resize(self, event):
        w, h = event.width, event.height
        if w < 100 or h < 200:
            return
        self.r = max(60, min(w / 2 - 35, (h - 140) / 2 - 10))
        self.cx = w / 2
        self.cy = self.r + 25
        self.draw_clock_face()
        self.draw_hands()

    def draw_clock_face(self):
        c, cx, cy, r = self.clock_canvas, self.cx, self.cy, self.r
        c.delete("face")
        c.create_oval(cx - r - 14, cy - r - 14, cx + r + 14, cy + r + 14,
                      fill=BLUE, outline=LIGHT_TEXT, width=3, tags="face")
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill="white", outline=NAVY, width=3, tags="face")
        for i in range(60):
            a = math.radians(i * 6)
            length, width = (r * 0.09, 4) if i % 5 == 0 else (r * 0.04, 1)
            c.create_line(cx + (r - 5) * math.sin(a), cy - (r - 5) * math.cos(a),
                          cx + (r - 5 - length) * math.sin(a),
                          cy - (r - 5 - length) * math.cos(a),
                          width=width, fill=NAVY, tags="face")
        size = max(12, int(r * 0.11))
        for n in range(1, 13):
            a = math.radians(n * 30)
            c.create_text(cx + (r * 0.76) * math.sin(a), cy - (r * 0.76) * math.cos(a),
                          text=str(n), font=(FONT, size, "bold"), fill=NAVY, tags="face")
        c.tag_lower("face")

    def _hand(self, angle_deg, length, width, color):
        a = math.radians(angle_deg)
        self.clock_canvas.create_line(
            self.cx, self.cy, self.cx + length * math.sin(a), self.cy - length * math.cos(a),
            width=width, fill=color, capstyle=ROUND, tags="hands")

    def draw_hands(self):
        if self.r <= 0:
            return
        c = self.clock_canvas
        c.delete("hands")
        now = datetime.now()
        sec = now.second
        minute = now.minute + sec / 60
        hour = (now.hour % 12) + minute / 60
        self._hand(hour * 30, self.r * 0.50, max(5, self.r * 0.04), NAVY)
        self._hand(minute * 6, self.r * 0.75, max(3, self.r * 0.025), BLUE)
        self._hand(sec * 6, self.r * 0.85, 2, ACCENT)
        c.create_oval(self.cx - 8, self.cy - 8, self.cx + 8, self.cy + 8,
                      fill=ACCENT, outline="white", tags="hands")
        c.create_text(self.cx, self.cy + self.r + 55, text=now.strftime("%I:%M:%S %p"),
                      font=(FONT, 26, "bold"), fill="white", tags="hands")
        c.create_text(self.cx, self.cy + self.r + 92, text=now.strftime("%A, %d %B %Y"),
                      font=(FONT, 14), fill=LIGHT_TEXT, tags="hands")

    def update_clock(self):
        self.draw_hands()
        self.root.after(1000, self.update_clock)

    # ==================== MODULE WINDOWS ====================
    def open_module(self, key, cls):
        """Open a module once; clicking again just brings the existing window forward."""
        entry = self.windows.get(key)
        if entry and entry[0].winfo_exists():
            win = entry[0]
            win.deiconify()
            win.lift()
            win.focus_force()
            return
        win = Toplevel(self.root)
        try:
            obj = cls(win, self.user)
        except Exception as ex:
            win.destroy()
            messagebox.showerror("Error", f"Could not open this window:\n{ex}",
                                 parent=self.root)
            return
        self.windows[key] = (win, obj)

    # ==================== LOGOUT / EXIT ====================
    def logout(self):
        if messagebox.askyesno("Confirm", "Do you really want to logout?", parent=self.root):
            self.next_screen = ("login", None)
            self.root.destroy()

    def exit_app(self):
        if messagebox.askyesno("Confirm", "Do you really want to exit?", parent=self.root):
            self.root.destroy()

    # ==================== LIVE COUNTS ====================
    def update_counts(self):
        try:
            with get_conn() as con:
                counts = [con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                          for t in ("course", "student", "result")]
                pending = (con.execute("SELECT COUNT(*) FROM users WHERE role = 'pending'")
                           .fetchone()[0] if self.btn_users is not None else 0)
            for label, value in zip((self.lbl_course, self.lbl_student, self.lbl_result), counts):
                label.config(text=str(value))
            if self.btn_users is not None:
                self.btn_users.config(text=f"👥  Users ({pending})" if pending else "👥  Users")
        except sqlite3.Error:
            # show a dash instead of popping an error box every 5 seconds
            for label in (self.lbl_course, self.lbl_student, self.lbl_result):
                label.config(text="-")
        self.root.after(5000, self.update_counts)
