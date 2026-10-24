import shutil
import subprocess
import sys
from pathlib import Path

from endcall import __version__

ROOT = Path(__file__).resolve().parent
TESSERACT_SRC = ROOT / "Tesseract-OCR"
TESSERACT_MIN = ROOT / "build" / "Tesseract-OCR"
ASSETS = ROOT / "assets"
DIST = ROOT / "dist"


def stage_tesseract():
    exe = TESSERACT_SRC / "tesseract.exe"
    if not exe.is_file():
        sys.exit("Tesseract-OCR/tesseract.exe not found. See README > Tesseract.")

    if TESSERACT_MIN.exists():
        shutil.rmtree(TESSERACT_MIN)
    (TESSERACT_MIN / "tessdata").mkdir(parents=True)

    shutil.copy2(exe, TESSERACT_MIN)
    for dll in TESSERACT_SRC.glob("*.dll"):
        shutil.copy2(dll, TESSERACT_MIN)
    shutil.copy2(TESSERACT_SRC / "tessdata" / "eng.traineddata", TESSERACT_MIN / "tessdata")
    license_file = TESSERACT_SRC / "doc" / "LICENSE"
    if license_file.is_file():
        shutil.copy2(license_file, TESSERACT_MIN / "LICENSE")


def clear_old_build():
    """Delete the previous build first, with a clear message if it's still running."""
    old = DIST / "EndCall"
    if not old.exists():
        return
    try:
        shutil.rmtree(old)
    except PermissionError:
        sys.exit("Can't replace dist/EndCall because it's in use. Close EndCall.exe "
                 "(check Task Manager) and any Explorer window showing that folder, then try again.")


def main():
    clear_old_build()
    stage_tesseract()
    args = [
        sys.executable, "-m", "PyInstaller", "main.py",
        "--name", "EndCall",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--add-data", f"{TESSERACT_MIN};Tesseract-OCR",
    ]
    if ASSETS.is_dir():
        args += ["--add-data", f"{ASSETS};assets"]
    if (ASSETS / "logo.ico").is_file():
        args += ["--icon", str(ASSETS / "logo.ico")]

    subprocess.run(args, cwd=ROOT, check=True)

    zip_base = DIST / f"EndCall-{__version__}-windows"
    shutil.make_archive(str(zip_base), "zip", DIST, "EndCall")
    print(f"\nDone: {DIST / 'EndCall' / 'EndCall.exe'}\nZip:  {zip_base}.zip")


if __name__ == "__main__":
    main()
