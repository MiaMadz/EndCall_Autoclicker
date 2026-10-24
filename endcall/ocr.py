import hashlib
import re
import threading
import time
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageGrab

from .config import DATA_DIR

DEBUG_DIR = DATA_DIR / "debug"
DEBUG_KEEP = 10  # how many unreadable captures to keep

DIGITS_ONLY = "-c tessedit_char_whitelist=0123456789"
# Tesseract is most accurate when digits are about this many pixels tall, so the
# number is cropped and resized to each of these heights. A read only counts
# when at least two of them agree.
HEIGHTS = (32, 24, 28)

# Each Tesseract call starts a separate program (~150 ms), so the three reads
# run side by side instead of one after another.
_pool = ThreadPoolExecutor(max_workers=len(HEIGHTS))


def use_tesseract(path):
    pytesseract.pytesseract.tesseract_cmd = path


def grab(region):
    """Screenshot of a [x, y, w, h] region."""
    x, y, w, h = region
    return ImageGrab.grab(bbox=(x, y, x + w, y + h))


# ---------------------------------------------------------------- image cleanup

def _black_on_white(img):
    gray = np.array(img.convert("L"))
    if min(gray.shape) < 60:  # tiny captures: enlarge before thresholding
        gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # The edges of the box are background, so use them to decide which way to flip.
    edges = np.concatenate([bw[0], bw[-1], bw[:, 0], bw[:, -1]])
    if edges.mean() < 127:
        bw = 255 - bw
    return bw


def _crop_to_digits(bw):
    ys, xs = np.where(bw == 0)
    if len(ys) == 0:
        return None
    return bw[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _resize_to_height(crop, height):
    scale = height / crop.shape[0]
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    out = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=interp)
    _, out = cv2.threshold(out, 127, 255, cv2.THRESH_BINARY)
    return cv2.copyMakeBorder(out, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)


def prepare(img, height=HEIGHTS[0]):
    """The cleaned-up image Tesseract reads (black digits, white background)."""
    crop = _crop_to_digits(_black_on_white(img))
    return None if crop is None else _resize_to_height(crop, height)


# ---------------------------------------------------------------- Tesseract

def _read_once(bw):
    for psm in (7, 8):  # 7 = one line of text, 8 = one word
        digits = re.sub(r"\D", "", pytesseract.image_to_string(bw, config=f"--psm {psm} {DIGITS_ONLY}"))
        if digits:
            return int(digits) if len(digits) <= 4 else None
    return None


def _tesseract_vote(crop):
    """Read at every height in parallel. Returns (number or None, unanimous)."""
    reads = list(_pool.map(lambda h: _read_once(_resize_to_height(crop, h)), HEIGHTS))
    votes = Counter(r for r in reads if r is not None)
    if not votes:
        return None, False
    number, count = votes.most_common(1)[0]
    if count < 2:
        return None, False
    return number, count == len(HEIGHTS)


def _digit_count_matches(glyphs, number):
    """False if the digits on screen clearly don't match the number of digits read
    (e.g. two separate digits on screen but Tesseract returned '8' for '88')."""
    return glyphs is None or len(glyphs) == len(str(number))


def read_number(img):
    """Read the participant number from an image with Tesseract. Returns an int or None."""
    crop = _crop_to_digits(_black_on_white(img))
    if crop is None:
        return None
    number = _tesseract_vote(crop)[0]
    if number is not None and not _digit_count_matches(_split_digits(crop), number):
        return None
    return number


# ---------------------------------------------------------------- learned digits

GLYPH_W, GLYPH_H = 16, 24
MATCH_MAX = 0.12      # how different a digit may look from what was learned
MATCH_MARGIN = 0.05   # ...and how much closer it must be than any other digit
TEMPLATES_PER_DIGIT = 5
MAX_DIGIT_ASPECT = 0.9  # a single digit is never wider than this (width / height)


def _split_digits(crop):
    """Cut the cropped number into one image per digit, left to right.

    Returns None if two digits seem to be touching, since they can't be told apart.
    """
    ink = (crop == 0).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    boxes = sorted(stats[i, :4].tolist() for i in range(1, n) if stats[i, 4] > 2)
    # Join pieces that sit above each other (a digit broken in two by thresholding).
    merged = []
    for x, y, w, h in boxes:
        if merged:
            mx, my, mw, mh = merged[-1]
            overlap = min(mx + mw, x + w) - max(mx, x)
            if overlap > 0.5 * min(mw, w):
                nx, ny = min(mx, x), min(my, y)
                merged[-1] = [nx, ny, max(mx + mw, x + w) - nx, max(my + mh, y + h) - ny]
                continue
        merged.append([x, y, w, h])
    height = crop.shape[0]
    glyphs = []
    for x, y, w, h in merged:
        if h < 0.5 * height:  # specks, dots, commas
            continue
        if w / height > MAX_DIGIT_ASPECT:
            return None
        piece = crop[:, x:x + w]
        shape = cv2.resize(piece, (GLYPH_W, GLYPH_H), interpolation=cv2.INTER_AREA) / 255.0
        glyphs.append((shape, w / height))
    return glyphs


def _distance(a, b):
    shape_a, aspect_a = a
    shape_b, aspect_b = b
    return float(np.abs(shape_a - shape_b).mean()) + abs(aspect_a - aspect_b)


class Reader:
    """Reads one screen region fast by remembering what it has already seen.

    1. A capture identical to an earlier one returns the earlier answer.
    2. Digits Tesseract has read with full confidence are remembered, so new
       numbers made of known digits are matched directly in a few milliseconds.
    3. Anything else goes to Tesseract.
    """

    def __init__(self):
        self.seen = OrderedDict()  # capture fingerprint -> number
        self.templates = {}        # "0".."9" -> list of learned glyphs
        self.lock = threading.Lock()

    def read(self, img):
        with self.lock:
            return self._read(img)

    def _read(self, img):
        key = hashlib.blake2b(img.tobytes(), digest_size=16).digest() + bytes(str(img.size), "ascii")
        if key in self.seen:
            self.seen.move_to_end(key)
            return self.seen[key]

        crop = _crop_to_digits(_black_on_white(img))
        if crop is None:
            return None
        glyphs = _split_digits(crop)

        number = self._match(glyphs)
        if number is None:
            number, unanimous = _tesseract_vote(crop)
            if number is not None and not _digit_count_matches(glyphs, number):
                number = None
            if number is not None and unanimous:
                self._learn(glyphs, str(number))

        if number is not None:
            self.seen[key] = number
            if len(self.seen) > 300:
                self.seen.popitem(last=False)
        return number

    def _match(self, glyphs):
        if not glyphs or len(glyphs) > 4:  # None = touching digits
            return None
        text = ""
        for glyph in glyphs:
            scores = sorted(
                (min(_distance(glyph, t) for t in temps), digit)
                for digit, temps in self.templates.items()
            )
            if not scores or scores[0][0] > MATCH_MAX:
                return None  # a digit it hasn't learned yet
            if len(scores) > 1 and scores[1][0] - scores[0][0] < MATCH_MARGIN:
                return None  # looks too much like two different digits
            text += scores[0][1]
        return int(text)

    def _learn(self, glyphs, text):
        if not glyphs or len(glyphs) != len(text):
            return  # digits touching or split oddly: don't guess which is which
        for glyph, digit in zip(glyphs, text):
            # If this looks like a different digit learned earlier, one of them was
            # a misread: forget both rather than keep a wrong template.
            for other, temps in list(self.templates.items()):
                if other != digit and any(_distance(glyph, t) < MATCH_MAX / 2 for t in temps):
                    self.templates.pop(other, None)
                    self.templates.pop(digit, None)
                    return
            temps = self.templates.setdefault(digit, [])
            if len(temps) < TEMPLATES_PER_DIGIT and all(_distance(glyph, t) > 0.02 for t in temps):
                temps.append(glyph)


# ---------------------------------------------------------------- helpers

def read_count(region, reader):
    """Returns (number or None, the captured image)."""
    img = grab(region)
    return reader.read(img), img


def save_unreadable(img):
    """Keep a copy of a capture that couldn't be read, to see what went wrong."""
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
        img.save(DEBUG_DIR / f"{stamp}-captured.png")
        processed = prepare(img)
        if processed is not None:
            cv2.imwrite(str(DEBUG_DIR / f"{stamp}-processed.png"), processed)
        files = sorted(DEBUG_DIR.glob("*.png"))
        for old in files[:-DEBUG_KEEP * 2]:
            old.unlink()
    except OSError:
        pass


def processed_preview(img):
    """What Tesseract actually sees, as a PIL image (for the Test read preview)."""
    processed = prepare(img, height=48)
    return img if processed is None else Image.fromarray(processed)


def fit_image(img, max_w, max_h, max_scale=2.0):
    scale = min(max_w / img.width, max_h / img.height, max_scale)
    size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    return img.resize(size, Image.LANCZOS)
