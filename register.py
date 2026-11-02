from tkinter import *
from PIL import Image, ImageTk
from tkinter import ttk, messagebox

import auth
import config
from theme import (ACCENT, ACCENT_HOVER, CARD_BG, FONT, LIGHT_TEXT, MUTED, NAVY, PAGE_BG,
                   RED, GREEN, apply_theme)
from validators import password_strength
from widgets import make_entry

STRENGTH_COLORS = {"Weak": RED, "Fair": "#c77700", "Strong": GREEN, "": MUTED}


class Register:
    def __init__(self, root):
        self.root = root
        self.next_screen = (None, None)      # read by main.py after the window closes
        self.root.title("Registration Window")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.minsize(1000, 700)
        self.root.config(bg=PAGE_BG)

        apply_theme(self.root)
        self.build_background()
        self.build_card()
        self.root.bind("<Return>", lambda e: self.register_data())

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
        card.place(relx=0.5, rely=0.5, anchor="center", width=1000, height=640)

        left = Frame(card, bg=NAVY, width=330)
        left.pack(side=LEFT, fill=Y)
        left.pack_propagate(False)
        try:
            side = Image.open(config.image_path("side.jpg")).resize((330, 400),
                                                                    Image.Resampling.LANCZOS)
            self.side = ImageTk.PhotoImage(side)
            Label(left, image=self.side, bd=0, bg=NAVY).pack(side=TOP)
        except Exception:
            Label(left, text="🎓", font=(FONT, 90), bg=NAVY, fg="white"
                  ).pack(side=TOP, pady=(60, 40))

        Label(left, text="Welcome!", font=(FONT, 22, "bold"), bg=NAVY, fg="white"
              ).pack(pady=(18, 2))
        Label(left, text="Already have an account?", font=(FONT, 12), bg=NAVY, fg=LIGHT_TEXT
              ).pack()
        self.btn_login = Label(left, text="SIGN IN  →", font=(FONT, 13, "bold"),
                               bg="white", fg=NAVY, cursor="hand2")
        self.btn_login.pack(pady=18, ipadx=40, ipady=8)
        self.btn_login.bind("<Button-1>", lambda e: self.login())
        self.btn_login.bind("<Enter>", lambda e: self.btn_login.config(bg="#d6e6f2"))
        self.btn_login.bind("<Leave>", lambda e: self.btn_login.config(bg="white"))

        Frame(card, bg=ACCENT, width=4).pack(side=LEFT, fill=Y)

        form = Frame(card, bg=CARD_BG)
        form.pack(side=LEFT, fill=BOTH, expand=True, padx=40, pady=22)
        form.columnconfigure(0, weight=1, uniform="f")
        form.columnconfigure(1, weight=1, uniform="f")

        Label(form, text="CREATE ACCOUNT", font=(FONT, 24, "bold"), bg=CARD_BG, fg=NAVY
              ).grid(row=0, column=0, columnspan=2, sticky="w")
        Label(form, text="Fill in the details below to register", font=(FONT, 12),
              bg=CARD_BG, fg=MUTED).grid(row=1, column=0, columnspan=2, sticky="w")
        Frame(form, bg=ACCENT, height=3, width=70).grid(row=2, column=0, sticky="w",
                                                        pady=(6, 10))

        self.txt_fname = self.make_field(form, "First Name", 3, 0)
        self.txt_lname = self.make_field(form, "Last Name", 3, 1)
        self.txt_contact = self.make_field(form, "Contact No.", 5, 0)
        self.txt_email = self.make_field(form, "Email", 5, 1)

        Label(form, text="Security Question", font=(FONT, 12, "bold"), bg=CARD_BG, fg=NAVY
              ).grid(row=7, column=0, sticky="w", pady=(8, 2))
        self.cmb_quest = ttk.Combobox(form, font=(FONT, 12), state="readonly",
                                      style="Srms.TCombobox")
        self.cmb_quest["values"] = ("Select",) + auth.SECURITY_QUESTIONS
        self.cmb_quest.current(0)
        self.cmb_quest.grid(row=8, column=0, sticky="ew", padx=(0, 10), ipady=4)
        self.txt_answer = self.make_field(form, "Security Answer", 7, 1)

        self.txt_password = self.make_field(form, "Password", 9, 0, show="*")
        self.txt_cpassword = self.make_field(form, "Confirm Password", 9, 1, show="*")
        self.txt_password.bind("<KeyRelease>", lambda e: self.update_strength())

        # show/hide on the left, live password-strength hint on the right
        self.var_show = IntVar()
        Checkbutton(form, text="Show passwords", variable=self.var_show,
                    command=self.toggle_password, font=(FONT, 11), bg=CARD_BG, fg=MUTED,
                    activebackground=CARD_BG, bd=0, highlightthickness=0
                    ).grid(row=11, column=0, sticky="w", pady=(8, 0))
        self.lbl_strength = Label(form, text="", font=(FONT, 11, "bold"), bg=CARD_BG, fg=MUTED)
        self.lbl_strength.grid(row=11, column=1, sticky="w", padx=(10, 0), pady=(8, 0))

        self.var_check = IntVar()
        Checkbutton(form, text="I Agree To The Terms & Conditions", variable=self.var_check,
                    font=(FONT, 12, "bold"), bg=CARD_BG, fg=NAVY, activebackground=CARD_BG,
                    bd=0, highlightthickness=0
                    ).grid(row=12, column=0, columnspan=2, sticky="w", pady=(4, 10))

        self.btn_register = Label(form, text="REGISTER NOW  →", font=(FONT, 14, "bold"),
                                  bg=ACCENT, fg="white", cursor="hand2")
        self.btn_register.grid(row=13, column=0, columnspan=2, sticky="ew", ipady=10)
        self.btn_register.bind("<Button-1>", lambda e: self.register_data())
        self.btn_register.bind("<Enter>", lambda e: self.btn_register.config(bg=ACCENT_HOVER))
        self.btn_register.bind("<Leave>", lambda e: self.btn_register.config(bg=ACCENT))

    def make_field(self, parent, label, row, col, show=None):
        pad = (0, 10) if col == 0 else (10, 0)
        Label(parent, text=label, font=(FONT, 12, "bold"), bg=CARD_BG, fg=NAVY
              ).grid(row=row, column=col, sticky="w", padx=pad, pady=(8, 2))
        entry = make_entry(parent, show=show, size=13)
        entry.grid(row=row + 1, column=col, sticky="ew", padx=pad, ipady=6)
        return entry

    def toggle_password(self):
        char = "" if self.var_show.get() else "*"
        self.txt_password.config(show=char)
        self.txt_cpassword.config(show=char)

    def update_strength(self):
        label = password_strength(self.txt_password.get())
        self.lbl_strength.config(text=f"Strength: {label}" if label else "",
                                 fg=STRENGTH_COLORS[label])

    # ==================== REGISTER ====================
    def register_data(self):
        question = self.cmb_quest.get()
        password, cpassword = self.txt_password.get(), self.txt_cpassword.get()

        # only what the form itself knows; every real rule lives in auth.register_user
        if password != cpassword:
            messagebox.showerror("Error", "Passwords do not match!", parent=self.root)
            return
        if self.var_check.get() != 1:
            messagebox.showerror("Error", "Please accept the Terms & Conditions!",
                                 parent=self.root)
            return

        result = auth.register_user(
            self.txt_fname.get(), self.txt_lname.get(), self.txt_contact.get(),
            self.txt_email.get(), "" if question == "Select" else question,
            self.txt_answer.get(), password)
        if not result.ok:
            messagebox.showerror("Error", result.message, parent=self.root)
            return

        if result.role == "admin":
            text = ("Registration completed!\n\nYou are the first user, so your account "
                    "has been made the Administrator.")
        else:
            text = ("Registration submitted!\n\nAn administrator must approve your account "
                    "before you can log in.")
        messagebox.showinfo("Success", text, parent=self.root)
        self.login()

    # ==================== NAVIGATION ====================
    def login(self):
        self.next_screen = ("login", None)
        self.root.destroy()
