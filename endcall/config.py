import json
import os
import shutil
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)

# Where bundled files (Tesseract-OCR, assets) live.
if FROZEN:
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    RESOURCE_DIR = Path(__file__).resolve().parent.parent

#Where settings are saved. The .exe may sit in a read-only folder, so it uses %APPDATA%\EndCall; running from source keeps config.json in the project.
if FROZEN:
    DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "EndCall"
else:
    DATA_DIR = RESOURCE_DIR

CONFIG_PATH = DATA_DIR / "config.json"
LOGO_PATH = RESOURCE_DIR / "assets" / "logo.png"
BUNDLED_TESSERACT = RESOURCE_DIR / "Tesseract-OCR" / "tesseract.exe"

DEFAULTS = {
    "button_region": None,   # [x, y, w, h] of the End Call button
    "count_region": None,    # [x, y, w, h] of the participant number
    "min_count": 2,          # end when the count is at or below this
    "drop_amount": 5,        # ...or when it falls by this many
    "drop_window": 10,       # ...within this many seconds
    "interval": 0.5,         # seconds between reads
    "tesseract_path": None,  # only used if the bundled copy is missing
}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except (FileNotFoundError, ValueError, OSError):
        pass
    return cfg


def save_config(cfg):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError:
        pass


def find_tesseract(saved_path=None):
    """Return the path to tesseract.exe, preferring the copy bundled with the app."""
    candidates = [
        BUNDLED_TESSERACT,
        saved_path,
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return str(path)
    return None
