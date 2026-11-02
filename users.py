"""Admin-only screen: approve registrations, change roles, unlock or delete accounts."""
from tkinter import *
from tkinter import ttk, messagebox

import auth
from theme import (BLUE, BLUE_HOVER, CARD_BG, FONT, GREEN, GREEN_HOVER, GREY, GREY_HOVER,
                   MUTED, NAVY, PAGE_BG, PENDING_BG, RED, RED_HOVER, STRIPE, apply_theme)
from widgets import card_title, make_button, make_card, page_header


class UserAdminClass:
    def __init__(self, root, user):
        self.root = root
        self.user = user
        self.rows = {}
        self.selected = None

        self.root.title("Student Result Management System")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.minsize(1000, 600)
        self.root.config(bg=PAGE_BG)
        self.root.focus_force()

        apply_theme(self.root)
        self.var_role = StringVar(value="viewer")
        page_header(self.root, "👥  MANAGE USERS", "Approve  •  Assign Roles  •  Unlock")
        self.build_body()
        self.refresh()

    def build_body(self):
        body = Frame(self.root, bg=PAGE_BG)
        body.pack(side=TOP, fill=BOTH, expand=True, padx=15, pady=15)
        card = make_card(body)
        card.pack(fill=BOTH, expand=True)

        top = Frame(card, bg=CARD_BG)
        top.pack(fill=X, padx=18, pady=(16, 6))
        card_title(top, "User Accounts").pack(side=LEFT)
        self.lbl_count = Label(top, text="", font=(FONT, 11), bg=CARD_BG, fg=MUTED)
        self.lbl_count.pack(side=RIGHT)
        Label(card, text="New registrations stay 'Pending' (highlighted) and cannot log in "
                         "until you give them a role.", font=(FONT, 11), bg=CARD_BG, fg=MUTED
              ).pack(anchor="w", padx=18, pady=(0, 8))

        # controls
        bar = Frame(card, bg=PAGE_BG)
        bar.pack(fill=X, padx=18, pady=(0, 10))
        Label(bar, text="Role", font=(FONT, 12, "bold"), bg=PAGE_BG, fg=NAVY
              ).pack(side=LEFT, padx=(12, 8), pady=10)
        ttk.Combobox(bar, textvariable=self.var_role, values=auth.ALL_ROLES, state="readonly",
                     width=12, font=(FONT, 12), style="Srms.TCombobox"
                     ).pack(side=LEFT, pady=10)
        make_button(bar, "✔  Apply Role", self.apply_role, GREEN, GREEN_HOVER
                    ).pack(side=LEFT, padx=(12, 6), pady=10, ipadx=10)
        make_button(bar, "🔓  Unlock Login", self.unlock, BLUE, BLUE_HOVER
                    ).pack(side=LEFT, padx=6, pady=10, ipadx=10)
        make_button(bar, "🗑  Delete User", self.delete, RED, RED_HOVER
                    ).pack(side=LEFT, padx=6, pady=10, ipadx=10)
        make_button(bar, "↻  Refresh", self.refresh, GREY, GREY_HOVER
                    ).pack(side=RIGHT, padx=12, pady=10, ipadx=10)

        wrap = Frame(card, bg=CARD_BG)
        wrap.pack(fill=BOTH, expand=True, padx=18, pady=(0, 18))
        scrolly = ttk.Scrollbar(wrap, orient=VERTICAL)
        cols = ("id", "name", "email", "contact", "role", "joined")
        self.UserTable = ttk.Treeview(wrap, columns=cols, show="headings",
                                      style="Srms.Treeview", yscrollcommand=scrolly.set)
        scrolly.config(command=self.UserTable.yview)
        scrolly.pack(side=RIGHT, fill=Y)
        self.UserTable.pack(fill=BOTH, expand=True)
        for key, text, width in (("id", "ID", 60), ("name", "Name", 200), ("email", "Email", 260),
                                 ("contact", "Contact", 130), ("role", "Role", 110),
                                 ("joined", "Registered", 160)):
            self.UserTable.heading(key, text=text)
            self.UserTable.column(key, width=width, minwidth=50, anchor="w")
        self.UserTable.tag_configure("odd", background=STRIPE)
        self.UserTable.tag_configure("even", background="white")
        self.UserTable.tag_configure("pending", background=PENDING_BG)
        self.UserTable.bind("<ButtonRelease-1>", self.on_select)

    # ==================== ACTIONS ====================
    def refresh(self):
        try:
            users = auth.list_users(self.user)
        except PermissionError as ex:
            messagebox.showerror("Access Denied", str(ex), parent=self.root)
            self.root.destroy()
            return
        self.UserTable.delete(*self.UserTable.get_children())
        self.rows.clear()
        self.selected = None
        pending = 0
        for i, u in enumerate(users):
            tag = "pending" if u["role"] == "pending" else ("even" if i % 2 == 0 else "odd")
            pending += u["role"] == "pending"
            iid = self.UserTable.insert(
                "", END, tags=(tag,),
                values=(u["id"], f"{u['first_name']} {u['last_name']}", u["email"],
                        u["contact"], auth.ROLE_LABELS[u["role"]], u["created_at"]))
            self.rows[iid] = tuple(u)
        extra = f"  •  {pending} awaiting approval" if pending else ""
        self.lbl_count.config(text=f"{len(users)} user{'s' if len(users) != 1 else ''}{extra}")

    def on_select(self, event=None):
        row = self.rows.get(self.UserTable.focus())
        if row:
            self.selected = row                 # (id, first, last, email, contact, role, created)
            self.var_role.set(row[5])

    def _need_selection(self):
        if self.selected is None:
            messagebox.showerror("Error", "Select a user from the list first", parent=self.root)
            return False
        return True

    def _report(self, result):
        ok, message = result
        (messagebox.showinfo if ok else messagebox.showerror)(
            "Success" if ok else "Error", message, parent=self.root)
        if ok:
            self.refresh()

    def apply_role(self):
        if self._need_selection():
            self._report(auth.set_role(self.user, self.selected[0], self.var_role.get()))

    def unlock(self):
        if self._need_selection():
            self._report(auth.unlock_account(self.user, self.selected[3]))

    def delete(self):
        if not self._need_selection():
            return
        if messagebox.askyesno("Confirm", f"Delete the account of {self.selected[3]}?",
                               parent=self.root):
            self._report(auth.delete_user(self.user, self.selected[0]))
