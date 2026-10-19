import time
import tkinter as tk

from PIL import ImageEnhance, ImageGrab, ImageTk

from .theme import C, FONT


def pick_region(root, prompt):
    root.withdraw()
    root.update()
    time.sleep(0.3)
    shot = ImageGrab.grab()

    result = {}
    top = tk.Toplevel(root)
    top.overrideredirect(True)
    top.geometry(f"{shot.width}x{shot.height}+0+0")
    top.attributes("-topmost", True)

    canvas = tk.Canvas(top, width=shot.width, height=shot.height,
                       highlightthickness=0, bd=0, cursor="crosshair")
    canvas.pack()
    dimmed = ImageTk.PhotoImage(ImageEnhance.Brightness(shot).enhance(0.4))
    canvas.create_image(0, 0, anchor="nw", image=dimmed)

    banner_bg = canvas.create_rectangle(0, 0, 0, 0, fill=C["card"], outline=C["line"])
    banner = canvas.create_text(
        shot.width // 2, 40,
        text=f"{prompt}    ·    Drag to select    ·    Esc to cancel",
        fill=C["text"], font=(FONT, 14, "bold"))
    x0, y0, x1, y1 = canvas.bbox(banner)
    canvas.coords(banner_bg, x0 - 22, y0 - 12, x1 + 22, y1 + 12)

    state = {"start": None, "photo": None, "img": None, "rect": None}

    def box(e):
        sx, sy = state["start"]
        return min(sx, e.x), min(sy, e.y), max(sx, e.x), max(sy, e.y)

    def on_press(e):
        state["start"] = (e.x, e.y)

    def on_drag(e):
        if not state["start"]:
            return
        l, t, r, b = box(e)
        if r - l < 2 or b - t < 2:
            return
        if state["img"]:
            canvas.delete(state["img"])
        state["img"] = canvas.create_image(l, t, anchor="nw", image=state["photo"])
        if state["rect"]:
            canvas.coords(state["rect"], l, t, r, b)
        else:
            state["rect"] = canvas.create_rectangle(l, t, r, b, outline=C["accent"], width=2)
        for item in (state["rect"], banner_bg, banner):
            canvas.tag_raise(item)

    def on_release(e):
        if not state["start"]:
            return
        l, t, r, b = box(e)
        if r - l >= 4 and b - t >= 4:
            result["region"] = [l, t, r - l, b - t]
            top.destroy()
        else:
            state["start"] = None

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    top.bind("<Escape>", lambda e: top.destroy())
    top.focus_force()
    top.grab_set()
    root.wait_window(top)
    root.deiconify()

    region = result.get("region")
    if not region:
        return None, None
    x, y, w, h = region
    return region, shot.crop((x, y, x + w, y + h))
