import re

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageGrab

DIGITS_ONLY = "--psm 7 -c tessedit_char_whitelist=0123456789"


def use_tesseract(path):
    pytesseract.pytesseract.tesseract_cmd = path


def grab(region):
    """Screenshot of a [x, y, w, h] region."""
    x, y, w, h = region
    return ImageGrab.grab(bbox=(x, y, x + w, y + h))


def prepare(img):
    arr = np.array(img.convert("L"))
    arr = cv2.resize(arr, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    _, arr = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if arr.mean() < 127:  # light text on a dark background, so flip it
        arr = 255 - arr
    return cv2.copyMakeBorder(arr, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)


def read_number(img):
    text = pytesseract.image_to_string(prepare(img), config=DIGITS_ONLY)
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def read_count(region):
    return read_number(grab(region))


def fit_image(img, max_w, max_h, max_scale=2.0):
    scale = min(max_w / img.width, max_h / img.height, max_scale)
    size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    return img.resize(size, Image.LANCZOS)
