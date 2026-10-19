import tkinter as tk

FONT = "Segoe UI"

C = {
    "bg": "#152036",
    "card": "#1F2E47",
    "card_hi": "#283A57",
    "line": "#2E4263",
    "text": "#E8EDF5",
    "muted": "#8D9BB3",
    "accent": "#4C8DFF",
    "accent_hi": "#6AA1FF",
    "ok": "#3DD68C",
    "warn": "#F5B544",
    "danger": "#FF5D5D",
    "danger_hi": "#FF7A7A",
}

BUTTON_KINDS = {
    "primary": (C["accent"], C["accent_hi"], "#FFFFFF"),
    "secondary": (C["card_hi"], C["line"], C["text"]),
    "danger": (C["danger"], C["danger_hi"], "#FFFFFF"),
}


def make_button(parent, text, command, kind="secondary", size=10, **kw):
    b = tk.Button(parent, text=text, command=command, relief="flat", bd=0,
                  cursor="hand2", font=(FONT, size, "bold"), padx=14, pady=7,
                  disabledforeground=C["muted"], **kw)
    set_button_kind(b, kind)
    b.bind("<Enter>", lambda e: b["state"] != "disabled" and b.config(bg=b.hover_bg))
    b.bind("<Leave>", lambda e: b.config(bg=b.base_bg))
    return b


def set_button_kind(b, kind):
    bg, hover, fg = BUTTON_KINDS[kind]
    b.base_bg, b.hover_bg = bg, hover
    b.config(bg=bg, fg=fg, activebackground=hover, activeforeground=fg)


def make_spin(parent, var, lo, hi, step=1, width=4):
    return tk.Spinbox(parent, from_=lo, to=hi, increment=step, textvariable=var,
                      width=width, font=(FONT, 11), justify="center",
                      bg=C["card_hi"], fg=C["text"], buttonbackground=C["line"],
                      relief="flat", bd=0, insertbackground=C["text"],
                      highlightthickness=1, highlightbackground=C["line"],
                      highlightcolor=C["accent"], disabledbackground=C["card"],
                      disabledforeground=C["muted"], readonlybackground=C["card_hi"])


def card(parent):
    outer = tk.Frame(parent, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
    inner = tk.Frame(outer, bg=C["card"])
    inner.pack(fill="both", expand=True, padx=16, pady=14)
    return outer, inner


def label(parent, text="", color="text", size=10, weight="normal", **kw):
    return tk.Label(parent, text=text, bg=parent["bg"], fg=C[color],
                    font=(FONT, size, weight), **kw)
