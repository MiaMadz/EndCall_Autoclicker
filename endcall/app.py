import time
import tkinter as tk
from collections import deque
from datetime import datetime
from tkinter import filedialog

import pyautogui
from PIL import Image, ImageTk

from . import config, ocr
from .monitor import Monitor
from .region_picker import pick_region
from .theme import C, FONT, card, label, make_button, make_spin, set_button_kind
from .trigger import TriggerRule

UNREADABLE_WARNING_AFTER = 5  #failed reads in a row before warning


def now_text(seconds=True):
    fmt = "%I:%M:%S %p" if seconds else "%I:%M %p"
    return datetime.now().strftime(fmt).lstrip("0")


class App:
    THUMB_W, THUMB_H = 230, 64

    def __init__(self, root):
        self.root = root
        self.cfg = config.load_config()
        self.monitor = Monitor(root, self._on_reading)
        self.rule = None
        self.unread_streak = 0
        self.recent = deque(maxlen=6)
        self.ui = {}
        self.thumb_photos = {}
        self.spins = []

        self.tesseract = config.find_tesseract(self.cfg.get("tesseract_path"))
        if self.tesseract:
            ocr.use_tesseract(self.tesseract)

        self._build()
        self._load_thumbs()
        self._refresh()

        if self.tesseract:
            self.log("Ready.")
        else:
            self.log("Tesseract OCR wasn't found. Click Locate to point to tesseract.exe.", "warn")

        root.protocol("WM_DELETE_WINDOW", self._close)

    @property
    def monitoring(self):
        return self.monitor.running

    #layout

    def _build(self):
        r = self.root
        r.title("EndCall")
        r.configure(bg=C["bg"])
        r.resizable(False, False)

        page = tk.Frame(r, bg=C["bg"])
        page.pack(fill="both", expand=True, padx=20, pady=18)

        self._build_header(page)
        self._build_count(page)
        self._build_setup(page)
        self._build_rules(page)
        self._build_tesseract_bar(page)

        self.start_btn = make_button(page, "Start monitoring", self._toggle, "primary", size=12)
        self.start_btn.config(pady=11)
        self.start_btn.pack(fill="x", pady=(0, 12))

        self._build_log(page)

    def _build_header(self, page):
        head = tk.Frame(page, bg=C["bg"])
        head.pack(fill="x")
        try:
            logo = Image.open(config.LOGO_PATH)
            self.icon = ImageTk.PhotoImage(logo)
            self.root.iconphoto(True, self.icon)
            self.logo_small = ImageTk.PhotoImage(ocr.fit_image(logo, 38, 38))
            tk.Label(head, image=self.logo_small, bg=C["bg"]).pack(side="left", padx=(0, 10))
        except OSError:
            pass  # no logo, no problem
        titles = tk.Frame(head, bg=C["bg"])
        titles.pack(side="left")
        label(titles, "EndCall", size=17, weight="bold").pack(anchor="w")
        label(titles, "Leaves the call for you when everyone else does", "muted", 9).pack(anchor="w")
        self.status = tk.Label(head, font=(FONT, 9, "bold"), padx=12, pady=4)
        self.status.pack(side="right")

    def _build_count(self, page):
        outer, inner = card(page)
        outer.pack(fill="x", pady=(16, 12))
        label(inner, "PARTICIPANTS", "muted", 9, "bold").pack(anchor="w")
        self.count_var = tk.StringVar(value="—")
        tk.Label(inner, textvariable=self.count_var, bg=C["card"], fg=C["text"],
                 font=(FONT, 44, "bold")).pack(anchor="w")
        self.count_sub = label(inner, "Not monitoring", "muted", 9)
        self.count_sub.pack(anchor="w")

    def _build_setup(self, page):
        setup = tk.Frame(page, bg=C["bg"])
        setup.pack(fill="x")
        setup.grid_columnconfigure((0, 1), weight=1, uniform="setup")
        self._setup_card(setup, 0, "1", "End Call button", "button_region",
                         "Select the End Call button")
        self._setup_card(setup, 1, "2", "Participant count", "count_region",
                         "Select just the participant number")

    def _setup_card(self, parent, col, step, title, key, prompt):
        outer, inner = card(parent)
        outer.grid(row=0, column=col, sticky="nsew", padx=(0, 6) if col == 0 else (6, 0))

        head = tk.Frame(inner, bg=C["card"])
        head.pack(fill="x")
        tk.Label(head, text=step, bg=C["accent"], fg="white", font=(FONT, 9, "bold"),
                 width=2).pack(side="left")
        label(head, title, size=11, weight="bold").pack(side="left", padx=8)

        box = tk.Frame(inner, bg=C["card_hi"], width=self.THUMB_W, height=self.THUMB_H + 12)
        box.pack(fill="x", pady=(10, 4))
        box.pack_propagate(False)
        thumb = tk.Label(box, bg=C["card_hi"], fg=C["muted"], text="Nothing selected", font=(FONT, 9))
        thumb.pack(expand=True)

        info = label(inner, "", "muted", 8)
        info.pack(anchor="w")

        btns = tk.Frame(inner, bg=C["card"])
        btns.pack(fill="x", pady=(8, 0))
        select = make_button(btns, "Select", lambda: self._select(key, prompt, title))
        select.pack(side="left")
        test = None
        if key == "count_region":
            test = make_button(btns, "Test read", self._test_read)
            test.pack(side="left", padx=(8, 0))

        self.ui[key] = {"thumb": thumb, "info": info, "select": select, "test": test}

    def _build_rules(self, page):
        outer, inner = card(page)
        outer.pack(fill="x", pady=12)
        label(inner, "When to end the call", size=11, weight="bold").pack(anchor="w", pady=(0, 8))

        self.v_min = tk.IntVar(value=self.cfg["min_count"])
        self.v_drop = tk.IntVar(value=self.cfg["drop_amount"])
        self.v_window = tk.IntVar(value=self.cfg["drop_window"])
        self.v_interval = tk.DoubleVar(value=self.cfg["interval"])

        def row(text):
            f = tk.Frame(inner, bg=C["card"])
            f.pack(fill="x", pady=3)
            label(f, text).pack(side="left")
            ctrl = tk.Frame(f, bg=C["card"])
            ctrl.pack(side="right")
            return ctrl

        def spin(parent, var, lo, hi, step=1):
            s = make_spin(parent, var, lo, hi, step)
            s.pack(side="left")
            self.spins.append(s)

        def unit(parent, text, padx=(6, 0)):
            label(parent, text, "muted", 10).pack(side="left", padx=padx)

        c = row("End when the count reaches or goes below")
        spin(c, self.v_min, 0, 999)
        unit(c, "people")

        c = row("Or when it drops by")
        spin(c, self.v_drop, 1, 999)
        unit(c, "within", padx=6)
        spin(c, self.v_window, 2, 120)
        unit(c, "sec")

        c = row("Check every")
        spin(c, self.v_interval, 0.5, 10, 0.5)
        unit(c, "sec")

        label(inner, "A number has to be read twice in a row before it counts, so one misread "
                     "won't end your call. The first rule only starts once the count has been "
                     "above that number, so joining an empty call early is safe.",
              "muted", 9, wraplength=500, justify="left"
              ).pack(anchor="w", pady=(8, 0))

    def _build_tesseract_bar(self, page):
        # Only shown when Tesseract can't be found.
        self.tess_bar = tk.Frame(page, bg=C["card"], highlightthickness=1, highlightbackground=C["warn"])
        inner = tk.Frame(self.tess_bar, bg=C["card"])
        inner.pack(fill="x", padx=14, pady=10)
        label(inner, "Tesseract OCR not found, so the count can't be read.", "warn", 10).pack(side="left")
        make_button(inner, "Locate…", self._locate_tesseract).pack(side="right")

    def _build_log(self, page):
        outer, inner = card(page)
        outer.pack(fill="x")
        label(inner, "ACTIVITY", "muted", 9, "bold").pack(anchor="w", pady=(0, 4))
        self.log_box = tk.Text(inner, height=5, bg=C["card"], fg=C["text"], relief="flat", bd=0,
                               font=(FONT, 9), wrap="word", highlightthickness=0,
                               cursor="arrow", state="disabled")
        self.log_box.pack(fill="x")
        for tag in ("muted", "ok", "warn", "danger"):
            self.log_box.tag_config(tag, foreground=C[tag])

    #state

    def _set_status(self, text, color):
        self.status.config(text=text, bg=color, fg=C["bg"])

    def _refresh(self):
        """Sync buttons, labels and the status badge with the current state."""
        busy = self.monitoring
        for key, w in self.ui.items():
            region = self.cfg.get(key)
            if region:
                x, y, rw, rh = region
                w["info"].config(text=f"at {x}, {y}  ·  {rw}×{rh}px")
                w["select"].config(text="Reselect")
            else:
                w["info"].config(text="")
                w["select"].config(text="Select")
            w["select"].config(state="disabled" if busy else "normal")
            if w["test"]:
                can_test = region and self.tesseract and not busy
                w["test"].config(state="normal" if can_test else "disabled")

        for s in self.spins:
            s.config(state="disabled" if busy else "normal")

        if self.tesseract:
            self.tess_bar.pack_forget()
        else:
            self.tess_bar.pack(fill="x", pady=(0, 12), before=self.start_btn)

        ready = bool(self.cfg.get("button_region") and self.cfg.get("count_region") and self.tesseract)
        if busy:
            self.start_btn.config(text="Stop monitoring", state="normal")
            set_button_kind(self.start_btn, "danger")
            self._set_status("WATCHING", C["ok"])
        else:
            self.start_btn.config(text="Start monitoring", state="normal" if ready else "disabled")
            set_button_kind(self.start_btn, "primary")
            if not ready:
                self._set_status("SETUP NEEDED", C["warn"])
            elif self.status["text"] != "CALL ENDED":
                self._set_status("READY", C["muted"])

    def _settings(self):
        """Read the rule inputs (clamped to sane values) and save them."""
        def get(var, lo, hi, fallback):
            try:
                return min(max(var.get(), lo), hi)
            except (tk.TclError, ValueError):
                return fallback

        d = config.DEFAULTS
        s = {
            "min_count": get(self.v_min, 0, 999, d["min_count"]),
            "drop_amount": get(self.v_drop, 1, 999, d["drop_amount"]),
            "drop_window": get(self.v_window, 2, 120, d["drop_window"]),
            "interval": get(self.v_interval, 0.5, 10, d["interval"]),
        }
        self.v_min.set(s["min_count"])
        self.v_drop.set(s["drop_amount"])
        self.v_window.set(s["drop_window"])
        self.v_interval.set(s["interval"])
        self.cfg.update(s)
        config.save_config(self.cfg)
        return s

    #setup actions

    def _set_thumb(self, key, img):
        w = self.ui[key]["thumb"]
        if img is None:
            w.config(image="", text="Nothing selected")
            return
        photo = ImageTk.PhotoImage(ocr.fit_image(img, self.THUMB_W, self.THUMB_H))
        self.thumb_photos[key] = photo  # keep a reference or Tk drops the image
        w.config(image=photo, text="")

    def _load_thumbs(self):
        for key in self.ui:
            region = self.cfg.get(key)
            if region:
                try:
                    self._set_thumb(key, ocr.grab(region))
                except Exception:
                    pass

    def _select(self, key, prompt, title):
        region, crop = pick_region(self.root, prompt)
        if not region:
            self.log("Selection cancelled.", "muted")
            return
        self.cfg[key] = region
        config.save_config(self.cfg)
        self._set_thumb(key, crop)
        self.log(f"{title} saved.")
        self._refresh()
        if key == "count_region" and self.tesseract:
            self._test_read()

    def _test_read(self):
        region = self.cfg.get("count_region")
        if not region:
            return
        img = ocr.grab(region)
        try:
            count = ocr.read_number(img)
        except Exception as e:
            self._set_thumb("count_region", img)
            self.log(f"OCR error: {e}", "danger")
            return
        # Show what Tesseract sees, so it's easy to spot icons or labels in the box.
        self._set_thumb("count_region", ocr.processed_preview(img))
        if count is None:
            ocr.save_unreadable(img)
            self.log("Couldn't read a number there. Try selecting only the digits.", "warn")
        else:
            self.count_var.set(str(count))
            self.count_sub.config(text="Test read")
            self.log(f"Test read: {count}", "ok")

    def _locate_tesseract(self):
        path = filedialog.askopenfilename(
            title="Find tesseract.exe",
            filetypes=[("tesseract.exe", "tesseract.exe"), ("All files", "*.*")])
        if not path:
            return
        self.tesseract = path
        ocr.use_tesseract(path)
        self.cfg["tesseract_path"] = path
        config.save_config(self.cfg)
        self.log("Tesseract found.", "ok")
        self._refresh()

    #monitoring

    def _toggle(self):
        if self.monitoring:
            self._stop()
            self.log("Monitoring stopped.", "muted")
        else:
            self._start()

    def _start(self):
        s = self._settings()
        self.rule = TriggerRule(s["min_count"], s["drop_amount"], s["drop_window"])
        self.unread_streak = 0
        self.recent = deque(maxlen=6)
        self.monitor.start(self.cfg["count_region"], s["interval"])
        self.count_sub.config(text="Starting…")
        self._refresh()
        self.log(f"Watching. Ends at {s['min_count']} or fewer, or a drop of "
                 f"{s['drop_amount']}+ within {s['drop_window']}s.", "ok")

    def _stop(self):
        self.monitor.stop()
        self.count_sub.config(text="Not monitoring")
        self._refresh()

    def _on_reading(self, now, count):
        if isinstance(count, Exception):
            self._stop()
            self.log(f"OCR error, stopped: {count}", "danger")
            return

        if count is None:
            self.unread_streak += 1
            self.count_sub.config(text=f"Can't read the count  ·  {now_text()}")
            if self.unread_streak == UNREADABLE_WARNING_AFTER:
                self.log("Can't read the count. Is the meeting window visible? "
                         f"Captures saved to {ocr.DEBUG_DIR}", "warn")
            return
        if self.unread_streak >= UNREADABLE_WARNING_AFTER:
            self.log("Reading the count again.", "muted")
        self.unread_streak = 0

        self.count_var.set(str(count))
        reason = self.rule.update(count, now)
        peak = self.rule.recent_peak
        if not self.recent or self.recent[-1] != count:
            self.recent.append(count)
        history = " → ".join(str(n) for n in self.recent)
        peak_text = f"  ·  peak {peak} in last {self.rule.drop_window}s" if peak is not None else ""
        self.count_sub.config(text=f"{history}{peak_text}  ·  {now_text()}")
        if reason:
            self._end_call(reason)

    def _end_call(self, reason):
        self._stop()
        x, y, w, h = self.cfg["button_region"]
        # Hide this window so it can't be in the way of the button.
        self.root.withdraw()
        self.root.update()
        time.sleep(0.15)
        try:
            original = pyautogui.position()
            pyautogui.click(x + w // 2, y + h // 2)
            pyautogui.moveTo(*original)
            self.log(f"Clicked End Call: {reason}.", "danger")
            self._set_status("CALL ENDED", C["danger"])
            self.count_sub.config(text=f"Ended: {reason}")
        except Exception as e:
            self.log(f"Couldn't click End Call: {e}", "danger")
        finally:
            self.root.deiconify()

    #misc

    def log(self, message, tag=None):
        """Add a line to the top of the activity log."""
        stamp = now_text(seconds=False)
        self.log_box.config(state="normal")
        self.log_box.insert("1.0", f"{stamp}   ", ("muted",))
        self.log_box.insert(f"1.{len(stamp) + 3}", message + "\n", (tag,) if tag else ())
        self.log_box.delete("200.0", "end")
        self.log_box.config(state="disabled")

    def _close(self):
        self.monitor.stop()
        try:
            self._settings()
        except Exception:
            pass
        self.root.destroy()
