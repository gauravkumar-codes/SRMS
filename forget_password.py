from tkinter import *
from tkinter import messagebox

import auth
from theme import (ACCENT, ACCENT_HOVER, BLUE, BLUE_HOVER, BORDER, CARD_BG, FIELD_BG, FONT,
                   MUTED, NAVY, PAGE_BG)
from widgets import make_entry

PLACEHOLDER = "Load your question using the button above."


class ForgetPassword:
    def __init__(self, root):
        self.root = root

    def forget_password(self):
        win = Toplevel(self.root)
        win.title("Forgot Password")
        win.resizable(False, False)
        win.configure(bg=PAGE_BG)
        win.transient(self.root)

        width, height = 520, 700
        x = (win.winfo_screenwidth() - width) // 2
        y = (win.winfo_screenheight() - height) // 2
        win.geometry(f"{width}x{height}+{x}+{y}")

        header = Frame(win, bg=NAVY, height=90)
        header.pack(side=TOP, fill=X)
        header.pack_propagate(False)
        Label(header, text="🔒  RESET PASSWORD", font=(FONT, 22, "bold"), bg=NAVY,
              fg="white").pack(expand=True)
        Frame(win, bg=ACCENT, height=3).pack(side=TOP, fill=X)

        card = Frame(win, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill=BOTH, expand=True, padx=25, pady=22)
        form = Frame(card, bg=CARD_BG)
        form.pack(fill=BOTH, expand=True, padx=28, pady=20)
        form.columnconfigure(0, weight=1)

        def make_label(text, row, top=0):
            Label(form, text=text, font=(FONT, 12, "bold"), bg=CARD_BG, fg=NAVY
                  ).grid(row=row, column=0, sticky="w", pady=(top, 3))

        def make_field(row, var=None, show=None):
            entry = make_entry(form, var, show=show, size=13)
            entry.grid(row=row, column=0, sticky="ew", ipady=7)
            return entry

        def make_button(text, row, bg, hover, command, top=0):
            btn = Label(form, text=text, font=(FONT, 13, "bold"), bg=bg, fg="white",
                        cursor="hand2")
            btn.grid(row=row, column=0, sticky="ew", pady=(top, 0), ipady=9)
            btn.bind("<Button-1>", lambda e: command())
            btn.bind("<Enter>", lambda e: btn.config(bg=hover))
            btn.bind("<Leave>", lambda e: btn.config(bg=bg))
            return btn

        # ===== Email =====
        make_label("Registered Email", 0)
        email_var = StringVar()
        email_entry = make_field(1, email_var)
        self.btn_get_question = make_button("GET SECURITY QUESTION  →", 2, BLUE, BLUE_HOVER,
                                            lambda: get_question(), top=12)

        # ===== Security question display =====
        make_label("Security Question", 3, top=16)
        q_box = Frame(form, bg=FIELD_BG, highlightbackground=BORDER, highlightthickness=1)
        q_box.grid(row=4, column=0, sticky="ew")
        question_label = Label(q_box, text=PLACEHOLDER, font=(FONT, 12), bg=FIELD_BG,
                               fg=MUTED, wraplength=380, justify="left", anchor="w",
                               padx=10, pady=10)
        question_label.pack(fill=X)

        # ===== Answer =====
        make_label("Security Answer", 5, top=16)
        answer_var = StringVar()
        make_field(6, answer_var)

        # ===== New password =====
        make_label("New Password", 7, top=16)
        password_var = StringVar()
        password_entry = make_field(8, password_var, show="*")
        show_var = IntVar()
        Checkbutton(form, text="Show password", variable=show_var,
                    command=lambda: password_entry.config(show="" if show_var.get() else "*"),
                    font=(FONT, 11), bg=CARD_BG, fg=MUTED, activebackground=CARD_BG,
                    bd=0, highlightthickness=0).grid(row=9, column=0, sticky="w", pady=(6, 0))

        question_loaded = {"value": False}

        def forget_question(*_):
            """Changing the e-mail invalidates the question that was loaded for it."""
            if question_loaded["value"]:
                question_loaded["value"] = False
                question_label.config(text=PLACEHOLDER, fg=MUTED, font=(FONT, 12))

        email_var.trace_add("write", forget_question)

        def get_question():
            email = email_var.get().strip()
            if not email:
                messagebox.showerror("Error", "Please enter your email.", parent=win)
                return
            try:
                question = auth.get_security_question(email)
            except Exception as ex:
                messagebox.showerror("Database Error", str(ex), parent=win)
                return
            question_loaded["value"] = True
            question_label.config(text=question, fg=BLUE, font=(FONT, 12, "bold"))

        def reset_password():
            if not question_loaded["value"]:
                messagebox.showerror("Error", "Please load your security question first.",
                                     parent=win)
                return
            ok, message = auth.reset_password(email_var.get(), answer_var.get(),
                                              password_var.get())
            if not ok:
                messagebox.showerror("Error", message, parent=win)
                return
            messagebox.showinfo("Success", message, parent=win)
            win.destroy()

        self.btn_reset_password = make_button("RESET PASSWORD  →", 10, ACCENT, ACCENT_HOVER,
                                              reset_password, top=20)

        def on_enter(event):
            # Enter loads the question first, and only then submits the reset
            if question_loaded["value"]:
                reset_password()
            else:
                get_question()

        win.bind("<Return>", on_enter)
        email_entry.focus_set()
