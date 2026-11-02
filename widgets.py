"""Small reusable widget factories so every window looks and behaves the same."""
from tkinter import *
from tkinter import messagebox

import auth
from theme import (ACCENT, BLUE, BLUE_HOVER, BORDER, CARD_BG, FIELD_BG, FONT, LIGHT_TEXT,
                   MUTED, NAVY, READONLY_BG)


def make_button(parent, text, command, bg=BLUE, hover=BLUE_HOVER, size=13):
    """Flat label-button with hover effect (same look as the dashboard buttons)."""
    lbl = Label(parent, text=text, font=(FONT, size, "bold"), bg=bg, fg="white",
                cursor="hand2", pady=9)
    lbl.bind("<Button-1>", lambda e: command())
    lbl.bind("<Enter>", lambda e: lbl.config(bg=hover))
    lbl.bind("<Leave>", lambda e: lbl.config(bg=bg))
    return lbl


def make_entry(parent, var=None, show=None, readonly=False, size=12):
    entry = Entry(parent, textvariable=var, font=(FONT, size), bg=FIELD_BG, fg=NAVY,
                  relief=FLAT, highlightthickness=1, highlightbackground=BORDER,
                  highlightcolor=BLUE, insertbackground=NAVY, insertwidth=2,
                  readonlybackground=READONLY_BG)
    if show:
        entry.config(show=show)
    if readonly:
        entry.config(state="readonly")
    return entry


def make_label(parent, text):
    return Label(parent, text=text, font=(FONT, 12, "bold"), bg=CARD_BG, fg=MUTED)


def make_card(parent):
    return Frame(parent, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)


def card_title(parent, text):
    row = Frame(parent, bg=CARD_BG)
    Frame(row, bg=ACCENT, width=5).pack(side=LEFT, fill=Y)
    Label(row, text=text, font=(FONT, 15, "bold"), bg=CARD_BG, fg=NAVY
          ).pack(side=LEFT, padx=10, pady=2)
    return row


def page_header(root, title, subtitle=""):
    """Navy title bar with the orange accent line underneath."""
    header = Frame(root, bg=NAVY, height=64)
    header.pack(side=TOP, fill=X)
    header.pack_propagate(False)
    Label(header, text=title, font=(FONT, 22, "bold"), bg=NAVY, fg="white"
          ).pack(side=LEFT, padx=25)
    if subtitle:
        Label(header, text=subtitle, font=(FONT, 12), bg=NAVY, fg=LIGHT_TEXT
              ).pack(side=RIGHT, padx=25)
    Frame(root, bg=ACCENT, height=3).pack(side=TOP, fill=X)


def require_permission(user, permission, parent, action="do this"):
    """Authoritative permission gate for write operations.

    Hiding a button is only cosmetic; this re-checks the user's current role in
    the database and shows an error when access is denied.
    """
    if auth.can_now(user, permission):
        return True
    messagebox.showerror("Access Denied", f"You do not have permission to {action}.",
                         parent=parent)
    return False
