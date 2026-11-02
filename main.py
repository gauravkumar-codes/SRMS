"""Application entry point:  python main.py

Screens never open each other directly. Each screen records where to go next in
`next_screen` and closes itself; this loop then opens the next one. That keeps
exactly one Tk root alive at a time (no nested mainloops) and avoids circular
imports between login, register and dashboard.
"""
import logging
from tkinter import Tk, messagebox

from db import init_db


def run():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        init_db()                       # creates / upgrades rms.db (backup is automatic)
    except Exception as ex:             # show a readable message instead of a console trace
        root = Tk()
        root.withdraw()
        messagebox.showerror("Database Error", f"Could not prepare the database:\n{ex}")
        root.destroy()
        return

    from login import Login
    from register import Register
    from dashboard import RMS

    screen, payload = "login", None
    while screen:
        root = Tk()
        if screen == "login":
            app = Login(root)
        elif screen == "register":
            app = Register(root)
        elif screen == "dashboard":
            app = RMS(root, payload)
        else:
            root.destroy()
            break
        root.mainloop()
        # closing the window with the X button leaves next_screen empty -> exit
        screen, payload = getattr(app, "next_screen", (None, None))


if __name__ == "__main__":
    run()
