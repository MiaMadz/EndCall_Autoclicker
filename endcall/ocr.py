import time

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageGrab
from pytesseract import Output

from .config import DATA_DIR

DEBUG_DIR = DATA_DIR / "debug"
DEBUG_KEEP = 10  # how many unreadable captures to keep

# Characters Tesseract often returns in place of digits.
LOOKALIKES = str.maketrans({"O": "0", "o": "0", "D": "0", "I": "1", "l": "1", "|": "1", "!": "1"})
DIGITLIKE = set("0123456789OoDIl|!")
PUNCTUATION = "()[]{}:;.,'\"-_~*#@&%$"


def use_tesseract(path):
    pytesseract.pytesseract.tesseract_cmd = path


def grab(region):
    """Screenshot of a [x, y, w, h] region."""
    x, y, w, h = region
    return ImageGrab.grab(bbox=(x, y, x + w, y + h))


def prepare(img, scale=4):
    """Turn a screenshot into black text on a white background for Tesseract."""
    gray = np.array(img.convert("L"))
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # The edges of the box are background, so use them to decide which way to flip.
    # (More reliable than the average, which big bold digits can tip the wrong way.)
    edges = np.concatenate([bw[0], bw[-1], bw[:, 0], bw[:, -1]])
    if edges.mean() < 127:
        bw = 255 - bw
    return cv2.copyMakeBorder(bw, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)


def _numbers_in(bw, psm):
    """Find words that are numbers, like '12' or '(12)'. Returns [(confidence, number)].

    Tesseract reads everything (labels, icons, numbers) as separate words, and only
    the number-shaped ones are kept. Forcing digits-only would turn letters and
    icons into fake digits instead (e.g. an icon next to '2' becoming '22').
    """
    data = pytesseract.image_to_data(bw, config=f"--psm {psm}", output_type=Output.DICT)
    found = []
    for text, conf in zip(data["text"], data["conf"]):
        core = text.strip().strip(PUNCTUATION)
        if (core and len(core) <= 4 and set(core) <= DIGITLIKE
                and any(c.isdigit() for c in core)):
            found.append((float(conf), int(core.translate(LOOKALIKES))))
    return found


def read_number(img):
    """Read the participant number from an image. Returns an int, or None."""
    bw = prepare(img)
    for psm in (6, 11):  # 6 = a block of text, 11 = scattered text
        found = _numbers_in(bw, psm)
        if found:
            return max(found)[1]  # most confident number
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
        cv2.imwrite(str(DEBUG_DIR / f"{stamp}-processed.png"), prepare(img))
        files = sorted(DEBUG_DIR.glob("*.png"))
        for old in files[:-DEBUG_KEEP * 2]:
            old.unlink()
    except OSError:
        pass


def processed_preview(img):
    """What Tesseract actually sees, as a PIL image (for the Test read preview)."""
    return Image.fromarray(prepare(img))


def fit_image(img, max_w, max_h, max_scale=2.0):
    scale = min(max_w / img.width, max_h / img.height, max_scale)
    size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    return img.resize(size, Image.LANCZOS)
