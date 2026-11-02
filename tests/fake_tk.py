"""A tiny stand-in for tkinter so the GUI modules can be exercised without a display.

It is NOT a renderer: it only models what the application logic depends on
(variables, entry/text contents, tree items, bindings, message boxes). Layout and
colours still have to be checked by running the real application.
"""
import sys
import types
from unittest import mock

CONSTANTS = dict(
    LEFT="left", RIGHT="right", TOP="top", BOTTOM="bottom", X="x", Y="y", BOTH="both",
    END="end", FLAT="flat", VERTICAL="vertical", HORIZONTAL="horizontal", WORD="word",
    ROUND="round", CENTER="center", NORMAL="normal", DISABLED="disabled", W="w", E="e",
    N="n", S="s", NW="nw", NSEW="nsew")


class Var:
    def __init__(self, master=None, value=None, name=None):
        self._v = value if value is not None else ""
        self._traces = []

    def get(self):
        return self._v

    def set(self, value):
        self._v = value
        for cb in list(self._traces):
            cb()

    def trace_add(self, mode, callback):
        self._traces.append(lambda: callback())


class StringVar(Var):
    def set(self, value):
        super().set(str(value))


class IntVar(Var):
    def __init__(self, master=None, value=0, name=None):
        super().__init__(master, value)


class Widget:
    instances = []
    toplevels = 0

    def __init__(self, master=None, **kw):
        self.master, self.kw, self.exists = master, dict(kw), True
        self.bindings = {}
        self.children = []
        if hasattr(master, "children"):
            master.children.append(self)
        Widget.instances.append(self)

    def __getattr__(self, name):                     # pack, grid, place, columnconfigure ...
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: None

    def __setitem__(self, key, value):
        self.kw[key] = value

    def __getitem__(self, key):
        return self.kw.get(key)

    def config(self, **kw):
        self.kw.update(kw)

    configure = config

    def bind(self, event, callback=None, add=None):
        self.bindings[event] = callback

    def click(self):
        self.bindings["<Button-1>"](None)

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080

    def winfo_exists(self):
        return self.exists

    def destroy(self):
        self.exists = False


class Entry(Widget):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.var = kw.get("textvariable")
        self.text = ""

    def get(self):
        return self.var.get() if self.var else self.text

    def insert(self, index, string):
        if self.var:
            self.var.set(self.var.get() + string)
        else:
            self.text += string

    def delete(self, first, last=None):
        if self.var:
            self.var.set("")
        else:
            self.text = ""


class Text(Widget):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.content = ""

    def _editable(self):
        return self.kw.get("state", "normal") != "disabled"      # Tk ignores edits when disabled

    def get(self, start, end=None):
        return self.content + "\n"                                # Tk always appends a newline

    def insert(self, index, string):
        if self._editable():
            self.content += string

    def delete(self, start, end=None):
        if self._editable():
            self.content = ""


class Combobox(Widget):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.var = kw.get("textvariable")

    def current(self, index=None):
        values = self.kw.get("values", ())
        if index is not None and self.var is not None:
            self.var.set(values[index])

    def set(self, value):
        if self.var is not None:
            self.var.set(value)
        else:
            self.kw["selected"] = value

    def get(self):
        return self.var.get() if self.var else self.kw.get("selected", "")


class Treeview(Widget):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.items, self.focus_id, self.selected, self._n = {}, "", (), 0

    def insert(self, parent, index, values=(), tags=()):
        self._n += 1
        iid = f"I{self._n:03d}"
        self.items[iid] = tuple(values)
        return iid

    def delete(self, *iids):
        for iid in iids:
            self.items.pop(iid, None)

    def get_children(self):
        return tuple(self.items)

    def focus(self, item=None):
        return self.focus_id

    def selection(self):
        return self.selected

    def selection_set(self, iid):
        self.selected = (iid,)


class Toplevel(Widget):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        Widget.toplevels += 1


class MessageBox:
    def __init__(self):
        self.calls, self.answer = [], True

    def _record(self, kind):
        def fn(title=None, message=None, **kw):
            self.calls.append((kind, title, message))
            return self.answer if kind == "askyesno" else None
        return fn

    def __getattr__(self, name):
        return self._record(name)

    def last(self):
        return self.calls[-1] if self.calls else None


def install():
    """Replace tkinter (+ttk/messagebox) and PIL.ImageTk with the fakes; return the messagebox."""
    tk = types.ModuleType("tkinter")
    for cls in ("Frame", "Label", "Canvas", "Scrollbar", "Checkbutton", "Tk"):
        setattr(tk, cls, type(cls, (Widget,), {}))
    tk.Entry, tk.Text, tk.Toplevel, tk.StringVar, tk.IntVar = Entry, Text, Toplevel, StringVar, IntVar
    for name, value in CONSTANTS.items():
        setattr(tk, name, value)

    ttk = types.ModuleType("tkinter.ttk")
    ttk.Combobox, ttk.Treeview = Combobox, Treeview
    ttk.Scrollbar = type("Scrollbar", (Widget,), {})
    class Style:
        def __init__(self, *a, **k): pass
        def theme_use(self, *a, **k): pass
        def configure(self, *a, **k): pass
        def map(self, *a, **k): pass
    ttk.Style = Style

    mb = MessageBox()
    messagebox_mod = types.ModuleType("tkinter.messagebox")
    messagebox_mod.__getattr__ = lambda name: getattr(mb, name)
    for fn in ("showinfo", "showerror", "showwarning", "askyesno"):
        setattr(messagebox_mod, fn, getattr(mb, fn))

    tk.ttk, tk.messagebox = ttk, messagebox_mod
    sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk, "tkinter.messagebox": messagebox_mod})

    image_tk = types.ModuleType("PIL.ImageTk")
    image_tk.PhotoImage = mock.MagicMock()
    sys.modules["PIL.ImageTk"] = image_tk
    import PIL
    PIL.ImageTk = image_tk
    return mb


def labels(text=None):
    """All created Label widgets (optionally those whose text contains `text`)."""
    found = [w for w in Widget.instances if type(w).__name__ == "Label"]
    return [w for w in found if text is None or text in str(w.kw.get("text", ""))]
