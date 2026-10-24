import re
import time

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
# when two of them agree.
HEIGHTS = (32, 24, 28)


def use_tesseract(path):
    pytesseract.pytesseract.tesseract_cmd = path


def grab(region):
    """Screenshot of a [x, y, w, h] region."""
    x, y, w, h = region
    return ImageGrab.grab(bbox=(x, y, x + w, y + h))


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


def _read_once(bw):
    for psm in (7, 8):  # 7 = one line of text, 8 = one word
        digits = re.sub(r"\D", "", pytesseract.image_to_string(bw, config=f"--psm {psm} {DIGITS_ONLY}"))
        if digits:
            return int(digits) if len(digits) <= 4 else None
    return None


def prepare(img, height=HEIGHTS[0]):
    """The cleaned-up image Tesseract reads (black digits, white background)."""
    crop = _crop_to_digits(_black_on_white(img))
    return None if crop is None else _resize_to_height(crop, height)


def read_number(img):
    """Read the participant number from an image. Returns an int, or None if unsure."""
    crop = _crop_to_digits(_black_on_white(img))
    if crop is None:
        return None
    seen = []
    for height in HEIGHTS:
        number = _read_once(_resize_to_height(crop, height))
        if number is not None and number in seen:
            return number
        seen.append(number)
    return None


def read_count(region):
    """Returns (number or None, the captured image)."""
    img = grab(region)
    return read_number(img), img


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
