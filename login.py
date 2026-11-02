from tkinter import *
from PIL import Image, ImageTk
from tkinter import messagebox

import auth
import config
from theme import (ACCENT, ACCENT_HOVER, BLUE, BLUE_HOVER, CARD_BG, FONT,
                   LIGHT_TEXT, MUTED, NAVY, PAGE_BG)
from widgets import make_entry


class Login:
    def __init__(self, root):
        self.root = root
        self.next_screen = (None, None)      # read by main.py after the window closes
        self.root.title("Login Window")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.minsize(1000, 650)
        self.root.config(bg=PAGE_BG)

        self.build_background()
        self.build_card()
        self.root.bind("<Return>", lambda e: self.login_data())

    # ==================== BACKGROUND ====================
    def build_background(self):
        self.bg_label = Label(self.root, bg=NAVY, bd=0)
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        try:
            self.bg_src = Image.open(config.image_path("b2.jpg"))
        except Exception:
            self.bg_src = None
        self.root.bind("<Configure>", self.on_window_resize)

    def on_window_resize(self, event):
        # only react to the main window, not to child widgets
        if event.widget is not self.root or self.bg_src is None:
            return
        if event.width < 10 or event.height < 10:
            return
        img = self.bg_src.resize((event.width, event.height), Image.Resampling.LANCZOS)
        self.bg_img = ImageTk.PhotoImage(img)
        self.bg_label.config(image=self.bg_img)

    # ==================== CARD ====================
    def build_card(self):
        card = Frame(self.root, bg=CARD_BG, highlightbackground=NAVY, highlightthickness=2)
        card.place(relx=0.5, rely=0.5, anchor="center", width=900, height=560)

        # ---------- Left panel ----------
        left = Frame(card, bg=NAVY, width=330)
        left.pack(side=LEFT, fill=Y)
        left.pack_propagate(False)
        try:
            side = Image.open(config.image_path("side.jpg")).resize((330, 340),
                                                                    Image.Resampling.LANCZOS)
            self.side = ImageTk.PhotoImage(side)
            Label(left, image=self.side, bd=0, bg=NAVY).pack(side=TOP)
        except Exception:
            Label(left, text="🎓", font=(FONT, 90), bg=NAVY, fg="white"
                  ).pack(side=TOP, pady=(50, 30))

        Label(left, text="Welcome Back!", font=(FONT, 22, "bold"), bg=NAVY, fg="white"
              ).pack(pady=(18, 2))
        Label(left, text="Student Result Management System", font=(FONT, 11),
              bg=NAVY, fg=LIGHT_TEXT).pack()
        Label(left, text="New here?", font=(FONT, 12), bg=NAVY, fg=LIGHT_TEXT
              ).pack(pady=(14, 0))

        self.btn_register = Label(left, text="REGISTER  →", font=(FONT, 13, "bold"),
                                  bg="white", fg=NAVY, cursor="hand2")
        self.btn_register.pack(pady=8, ipadx=34, ipady=7)
        self.btn_register.bind("<Button-1>", lambda e: self.open_register())
        self.btn_register.bind("<Enter>", lambda e: self.btn_register.config(bg="#d6e6f2"))
        self.btn_register.bind("<Leave>", lambda e: self.btn_register.config(bg="white"))

        Frame(card, bg=ACCENT, width=4).pack(side=LEFT, fill=Y)

        # ---------- Right panel (form) ----------
        form = Frame(card, bg=CARD_BG)
        form.pack(side=LEFT, fill=BOTH, expand=True, padx=50, pady=30)
        form.columnconfigure(0, weight=1)

        Label(form, text="LOGIN", font=(FONT, 28, "bold"), bg=CARD_BG, fg=NAVY
              ).grid(row=0, column=0, sticky="w")
        Label(form, text="Sign in to access your dashboard", font=(FONT, 12),
              bg=CARD_BG, fg=MUTED).grid(row=1, column=0, sticky="w")
        Frame(form, bg=ACCENT, height=3, width=70).grid(row=2, column=0, sticky="w", pady=(6, 18))

        Label(form, text="Email", font=(FONT, 12, "bold"), bg=CARD_BG, fg=NAVY
              ).grid(row=3, column=0, sticky="w", pady=(0, 3))
        self.txt_email = make_entry(form, size=14)
        self.txt_email.grid(row=4, column=0, sticky="ew", ipady=8)

        Label(form, text="Password", font=(FONT, 12, "bold"), bg=CARD_BG, fg=NAVY
              ).grid(row=5, column=0, sticky="w", pady=(16, 3))
        self.txt_password = make_entry(form, show="*", size=14)
        self.txt_password.grid(row=6, column=0, sticky="ew", ipady=8)

        opts = Frame(form, bg=CARD_BG)
        opts.grid(row=7, column=0, sticky="ew", pady=(10, 0))
        self.var_show = IntVar()
        Checkbutton(opts, text="Show password", variable=self.var_show,
                    command=self.toggle_password, font=(FONT, 11), bg=CARD_BG, fg=MUTED,
                    activebackground=CARD_BG, bd=0, highlightthickness=0).pack(side=LEFT)

        self.btn_forget_password = Label(opts, text="Forgot Password?", font=(FONT, 12),
                                         bg=CARD_BG, fg=ACCENT, cursor="hand2")
        self.btn_forget_password.pack(side=RIGHT)
        self.btn_forget_password.bind("<Button-1>", lambda e: self.forget_password())
        self.btn_forget_password.bind(
            "<Enter>", lambda e: self.btn_forget_password.config(fg=ACCENT_HOVER))
        self.btn_forget_password.bind(
            "<Leave>", lambda e: self.btn_forget_password.config(fg=ACCENT))

        self.btn_login = Label(form, text="LOG IN  →", font=(FONT, 14, "bold"),
                               bg=ACCENT, fg="white", cursor="hand2")
        self.btn_login.grid(row=8, column=0, sticky="ew", pady=(26, 0), ipady=11)
        self.btn_login.bind("<Button-1>", lambda e: self.login_data())
        self.btn_login.bind("<Enter>", lambda e: self.btn_login.config(bg=ACCENT_HOVER))
        self.btn_login.bind("<Leave>", lambda e: self.btn_login.config(bg=ACCENT))

        link_row = Frame(form, bg=CARD_BG)
        link_row.grid(row=9, column=0, pady=(20, 0))
        Label(link_row, text="Don't have an account?", font=(FONT, 12),
              bg=CARD_BG, fg=MUTED).pack(side=LEFT)
        link = Label(link_row, text=" Register here", font=(FONT, 12, "bold"),
                     bg=CARD_BG, fg=BLUE, cursor="hand2")
        link.pack(side=LEFT)
        link.bind("<Button-1>", lambda e: self.open_register())
        link.bind("<Enter>", lambda e: link.config(fg=BLUE_HOVER))
        link.bind("<Leave>", lambda e: link.config(fg=BLUE))

        self.txt_email.focus_set()

    def toggle_password(self):
        self.txt_password.config(show="" if self.var_show.get() else "*")

    # ==================== LOGIN ====================
    def login_data(self):
        result = auth.authenticate(self.txt_email.get(), self.txt_password.get())
        if not result.ok:
            messagebox.showerror("Login Failed", result.message, parent=self.root)
            self.txt_password.delete(0, END)         # never leave a failed password on screen
            return
        self.next_screen = ("dashboard", result.user)
        self.root.destroy()

    # ==================== NAVIGATION ====================
    def open_register(self):
        self.next_screen = ("register", None)
        self.root.destroy()

    def forget_password(self):
        from forget_password import ForgetPassword
        ForgetPassword(self.root).forget_password()
