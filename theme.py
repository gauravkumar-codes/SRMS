"""One place for the colour palette, fonts and ttk styles (used by every window)."""
from tkinter import ttk

FONT = "Helvetica"
NAVY = "#0f2740"
BLUE = "#0b5377"
BLUE_HOVER = "#1478a8"
PAGE_BG = "#eaf2f8"
ACCENT = "#e43b06"
ACCENT_HOVER = "#ff5722"
CARD_BG = "#ffffff"
FIELD_BG = "#f3f7fa"
BORDER = "#cdd9e3"
MUTED = "#5f7080"
LIGHT_TEXT = "#9fc4de"
READONLY_BG = "#e3ebf2"
STRIPE = "#f3f8fc"
PENDING_BG = "#fff3e0"
LIGHT_BLUE = "#1e88e5"
GREEN = "#2e9e4f"
GREEN_HOVER = "#3fb862"
RED = "#b71c1c"
RED_HOVER = "#e53935"
GREY = "#37474f"
GREY_HOVER = "#546e7a"


def apply_theme(root):
    """Configure ttk widgets (tables, combo boxes, scrollbars) to match the app."""
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure("Srms.Treeview", font=(FONT, 11), rowheight=30, background="white",
                    fieldbackground="white", foreground=NAVY, borderwidth=0)
    style.configure("Srms.Treeview.Heading", font=(FONT, 11, "bold"), background=NAVY,
                    foreground="white", relief="flat", padding=(8, 8))
    style.map("Srms.Treeview", background=[("selected", BLUE)],
              foreground=[("selected", "white")])
    style.map("Srms.Treeview.Heading", background=[("active", BLUE)])

    style.configure("Srms.TCombobox", padding=5, fieldbackground=FIELD_BG,
                    background=FIELD_BG, foreground=NAVY, arrowcolor=BLUE)
    style.map("Srms.TCombobox", fieldbackground=[("readonly", FIELD_BG)],
              foreground=[("readonly", NAVY)])

    for orient in ("Vertical", "Horizontal"):
        style.configure(f"{orient}.TScrollbar", background=BORDER, troughcolor=PAGE_BG,
                        arrowcolor=NAVY, borderwidth=0)
    root.option_add("*TCombobox*Listbox.font", (FONT, 12))
