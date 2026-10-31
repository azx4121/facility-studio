"""Application widget adapters; no global patching of Tk or engineering models.

Comboboxes keep canonical variables and expose translated choices to the user.
Read-only labels, trees, canvases and report panes redraw in place on switching.
"""

import tkinter as native
from tkinter import (
    ttk as native_ttk,
    filedialog as native_files,
    messagebox as native_messages,
)
from types import SimpleNamespace
import weakref

from . import i18n


class Display:
    def __init__(self, master=None, **kwargs):
        self._source_text = None
        self._source_variable = None
        self._display_variable = None
        self._text_trace = None
        self._capture(kwargs, master)
        super().__init__(master, **kwargs)
        i18n.subscribe(self)
        self.bind("<Destroy>", self._release, add="+")

    def _release(self, event):
        if event.widget is self and self._text_trace:
            try:
                self._source_variable.trace_remove("write", self._text_trace)
            except native.TclError:
                pass
            self._text_trace = None

    def _capture(self, options, master=None):
        if "text" in options:
            self._source_text = options["text"]
            options["text"] = i18n.translate(options["text"])
        if "textvariable" in options:
            source = options["textvariable"]
            if isinstance(source, native.Variable):
                if self._text_trace:
                    self._source_variable.trace_remove("write", self._text_trace)
                self._source_variable = source
                self._display_variable = native.StringVar(
                    master or self, i18n.translate(source.get())
                )
                self._text_trace = source.trace_add(
                    "write", lambda *args: self.refresh_language()
                )
                options["textvariable"] = self._display_variable

    def configure(self, cnf=None, **kwargs):
        if cnf is not None and not isinstance(cnf, dict):
            return super().configure(cnf, **kwargs)
        options = dict(cnf or {}, **kwargs)
        if not options:
            return super().configure()
        self._capture(options)
        return super().configure(**options)

    config = configure

    def refresh_language(self):
        if not self.winfo_exists():
            return
        if self._source_text is not None:
            super().configure(text=i18n.translate(self._source_text))
        if self._source_variable is not None:
            self._display_variable.set(i18n.translate(self._source_variable.get()))


class Combobox(native_ttk.Combobox):
    def __init__(self, master=None, **kwargs):
        self._canonical = None
        self._trace = None
        self._busy = False
        self._choices = tuple(kwargs.pop("values", ()))
        source = kwargs.pop("textvariable", None)
        self._display = native.StringVar(master)
        super().__init__(master, textvariable=self._display, **kwargs)
        self._set_source(source or native.StringVar(self))
        self._display_trace = self._display.trace_add("write", self._selected)
        i18n.subscribe(self)
        self.bind("<Destroy>", self._release, add="+")
        self.refresh_language()

    def _release(self, event):
        if event.widget is self:
            try:
                self._canonical.trace_remove("write", self._trace)
                self._display.trace_remove("write", self._display_trace)
            except native.TclError:
                pass

    def _set_source(self, value):
        if self._canonical is not None and self._trace:
            self._canonical.trace_remove("write", self._trace)
        self._canonical = (
            value
            if isinstance(value, native.Variable)
            else native.StringVar(self, name=value)
        )
        self._trace = self._canonical.trace_add(
            "write", lambda *args: self.refresh_language()
        )

    def _selected(self, *args):
        if not self._busy:
            self._canonical.set(
                i18n.canonical_choice(self._display.get(), self._choices)
            )

    def refresh_language(self):
        if not self.winfo_exists():
            return
        self._busy = True
        try:
            super().configure(values=[i18n.translate(x) for x in self._choices])
            self._display.set(i18n.translate(self._canonical.get()))
        finally:
            self._busy = False

    def configure(self, cnf=None, **kwargs):
        if cnf is not None and not isinstance(cnf, dict):
            return super().configure(cnf, **kwargs)
        options = dict(cnf or {}, **kwargs)
        if not options:
            return super().configure()
        if "values" in options:
            self._choices = tuple(options.pop("values"))
        if "textvariable" in options:
            self._set_source(options.pop("textvariable"))
        result = super().configure(**options) if options else None
        self.refresh_language()
        return result

    config = configure

    def cget(self, key):
        if key == "values":
            return self._choices
        if key == "textvariable":
            return str(self._canonical)
        return super().cget(key)

    def get(self):
        return self._canonical.get()

    def set(self, value):
        self._canonical.set(i18n.canonical_choice(value, self._choices))

    def current(self, index=None):
        if index is None:
            try:
                return self._choices.index(self.get())
            except ValueError:
                return -1
        self.set(self._choices[index])


class Notebook(native_ttk.Notebook):
    def __init__(self, *args, **kwargs):
        self._texts = {}
        super().__init__(*args, **kwargs)
        i18n.subscribe(self)

    def add(self, child, **kwargs):
        if "text" in kwargs:
            self._texts[str(child)] = kwargs["text"]
            kwargs["text"] = i18n.translate(kwargs["text"])
        return super().add(child, **kwargs)

    def tab(self, tab_id, option=None, **kwargs):
        if "text" in kwargs:
            self._texts[self.tabs()[self.index(tab_id)]] = kwargs["text"]
            kwargs["text"] = i18n.translate(kwargs["text"])
        return super().tab(tab_id, option, **kwargs)

    def refresh_language(self):
        for tab, text in self._texts.items():
            if tab in self.tabs():
                super().tab(tab, text=i18n.translate(text))


class Treeview(native_ttk.Treeview):
    def __init__(self, *args, **kwargs):
        self._headings, self._items = {}, {}
        super().__init__(*args, **kwargs)
        i18n.subscribe(self)

    def heading(self, column, option=None, **kwargs):
        if "text" in kwargs:
            self._headings[column] = kwargs["text"]
            kwargs["text"] = i18n.translate(kwargs["text"])
        return super().heading(column, option, **kwargs)

    def _capture_item(self, item, kwargs):
        stored = self._items.setdefault(item, {})
        for key in ("text", "values"):
            if key in kwargs:
                stored[key] = kwargs[key]
                kwargs[key] = (
                    [i18n.translate(x) for x in kwargs[key]]
                    if key == "values"
                    else i18n.translate(kwargs[key])
                )

    def insert(self, parent, index, iid=None, **kwargs):
        stored = dict(kwargs)
        for key in ("text", "values"):
            if key in kwargs:
                kwargs[key] = (
                    [i18n.translate(x) for x in kwargs[key]]
                    if key == "values"
                    else i18n.translate(kwargs[key])
                )
        item = super().insert(parent, index, iid, **kwargs)
        self._items[item] = {k: stored[k] for k in ("text", "values") if k in stored}
        return item

    def item(self, item, option=None, **kwargs):
        self._capture_item(item, kwargs)
        return super().item(item, option, **kwargs)

    def delete(self, *items):
        for item in items:
            self._items.pop(item, None)
        return super().delete(*items)

    def refresh_language(self):
        for column, text in self._headings.items():
            super().heading(column, text=i18n.translate(text))
        for item, stored in self._items.items():
            if self.exists(item):
                options = dict(stored)
                for key, value in options.items():
                    options[key] = (
                        [i18n.translate(x) for x in value]
                        if key == "values"
                        else i18n.translate(value)
                    )
                super().item(item, **options)


class Canvas(native.Canvas):
    def __init__(self, *args, **kwargs):
        self._texts = {}
        super().__init__(*args, **kwargs)
        i18n.subscribe(self)

    def create_text(self, *args, **kwargs):
        text = kwargs.get("text", "")
        kwargs["text"] = i18n.translate(text)
        item = super().create_text(*args, **kwargs)
        self._texts[item] = text
        return item

    def delete(self, *args):
        for tag in args:
            for item in self.find_withtag(tag):
                self._texts.pop(item, None)
        return super().delete(*args)

    def refresh_language(self):
        for item, text in self._texts.items():
            self.itemconfigure(item, text=i18n.translate(text))


class Text(native.Text):
    """Report views only. Editable user notes retain native Text semantics."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._report = None
        i18n.subscribe(self)

    def insert(self, index, chars, *args):
        if not self.get("1.0", "end-1c"):
            self._report = getattr(chars, "source", str(chars))
        else:
            self._report = None
        return super().insert(index, i18n.translate(chars), *args)

    def delete(self, index1, index2=None):
        self._report = None
        return super().delete(index1, index2)

    def refresh_language(self):
        if self._report is not None:
            state = self.cget("state")
            position = self.yview()[0]
            super().configure(state="normal")
            super().delete("1.0", "end")
            super().insert("1.0", i18n.translate(self._report))
            super().configure(state=state)
            self.yview_moveto(position)


class Dialogs:
    def __init__(self, module):
        self.module = module

    def __getattr__(self, name):
        original = getattr(self.module, name)

        def call(*args, **kwargs):
            args = tuple(i18n.translate(x) if isinstance(x, str) else x for x in args)
            for key in ("title", "message", "detail", "initialfile"):
                if key in kwargs:
                    kwargs[key] = i18n.translate(kwargs[key])
            if "filetypes" in kwargs:
                kwargs["filetypes"] = [
                    (i18n.translate(label), pattern)
                    for label, pattern in kwargs["filetypes"]
                ]
            return original(*args, **kwargs)

        return call


tk = SimpleNamespace(**{name: getattr(native, name) for name in dir(native)})
ttk = SimpleNamespace(**{name: getattr(native_ttk, name) for name in dir(native_ttk)})
for name in ("Label", "Button", "Checkbutton", "Radiobutton", "LabelFrame"):
    setattr(tk, name, type(name, (Display, getattr(native, name)), {}))
    setattr(ttk, name, type(name, (Display, getattr(native_ttk, name)), {}))
tk.Canvas, tk.Text = Canvas, Text
ttk.Combobox, ttk.Notebook, ttk.Treeview = Combobox, Notebook, Treeview
filedialog, messagebox = Dialogs(native_files), Dialogs(native_messages)


class WindowTitle:
    def __init__(self, window):
        self.window = weakref.ref(window)
        self.original = window.title
        self.text = self.original()
        window.title = self.title
        i18n.subscribe(self)

    def title(self, text=None):
        if text is None:
            return self.original()
        self.text = str(text)
        return self.original(i18n.translate(self.text))

    def refresh_language(self):
        window = self.window()
        if window is not None and window.winfo_exists():
            self.original(i18n.translate(self.text))


def attach_window(window):
    i18n.initialize()
    if not hasattr(window, "_language_title"):
        window._language_title = WindowTitle(window)
        window._language_title.refresh_language()


class LanguagePicker(native_ttk.Combobox):
    def __init__(self, master):
        self.choice = native.StringVar(master, i18n.LANGUAGES[i18n.language()])
        super().__init__(
            master,
            textvariable=self.choice,
            values=tuple(i18n.LANGUAGES.values()),
            state="readonly",
            width=13,
        )
        self.bind("<<ComboboxSelected>>", self.selected)
        i18n.subscribe(self)

    def selected(self, event=None):
        value = next(k for k, v in i18n.LANGUAGES.items() if v == self.choice.get())
        i18n.set_language(value)
        if i18n.saving_warning():
            messagebox.showwarning(
                "Language",
                "Language changed for this session. Your profile could not save the preference.",
                parent=self.winfo_toplevel(),
            )

    def refresh_language(self):
        self.choice.set(i18n.LANGUAGES[i18n.language()])
