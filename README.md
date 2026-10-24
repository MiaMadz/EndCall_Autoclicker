# EndCall

**Leaves the call for you when everyone else does.**

EndCall watches the participant count in your online meeting (Zoom, Google Meet, Teams, or any app that shows a number on screen). When the count gets low, or suddenly drops, it clicks the **End Call** button for you. No more sitting alone in a meeting after it has ended.

<!-- Add a screenshot: save it as assets/screenshot.png and uncomment the line below -->
<!-- ![EndCall screenshot](assets/screenshot.png) -->

## Features

- **Works with any meeting app.** It reads the number off your screen, so it doesn't need integrations or logins.
- **Two rules:** end the call when the count reaches a minimum, or when it drops by a set amount within a few seconds.
- **Follows the number sequence.** Small steps like 41 → 40 are tracked live, while a big jump has to be read twice before it counts, so one bad read can't end your call.
- **Accurate reading.** Each capture is read at several sizes and only accepted when the reads agree.
- **Near-instant.** EndCall learns what each digit looks like on your screen after the first few reads, then reads new numbers in about a millisecond instead of calling the OCR engine each time.
- **Safe to join early.** The minimum rule only turns on after the count has risen above it.
- **Drag to select.** You pick the button and the number by dragging a box straight on your screen.
- **Remembers your setup** between sessions.
- **OCR included.** Tesseract ships with the app, so there's nothing extra to install.

## Download

Get the latest `EndCall-x.x.x-windows.zip` from the [Releases](../../releases) page. Unzip it and run **`EndCall.exe`**.

> Windows may show a SmartScreen warning because the app isn't code-signed. Click **More info → Run anyway**.

## How to use

1. **Join your meeting** and open the participants panel so the count is visible.
2. In EndCall, click **Select** under **End Call button**, then drag a box around your meeting's leave/end button.
3. Click **Select** under **Participant count**, then drag a box around **just the number**. EndCall test-reads it right away.
4. Set your rules:
   | Rule | Default | Meaning |
   |---|---|---|
   | Reaches or goes below | 2 | End when this few people are left (starts once the count has been above it) |
   | Drops by … within … sec | 5 within 10 | End when lots of people leave at once |
   | Check every | 0.5 sec | How often the number is read (down to 0.25) |
5. Click **Start monitoring**. EndCall can be minimized, but **the meeting window has to stay visible** and in the same place.

When a rule triggers, EndCall clicks End Call, puts your mouse back where it was, and logs the reason.

### Tips

- Select only the digits, not the icon or the label next to them. Leave room for an extra digit (9 → 10). **Test read** shows exactly what EndCall sees.
- If the count can't be read, the captures are saved to a `debug` folder (next to `config.json`) so you can see what went wrong.
- If you move or resize the meeting window, select both areas again.
- EndCall only clicks the **End Call** button. If your app then asks "Leave meeting?", that confirmation still needs you.

## Run from source

Requires **Windows** and **Python 3.10+**.

```powershell
git clone https://github.com/MiaMadz/EndCall_Autoclicker.git
cd EndCall_Autoclicker

# with uv
uv venv
uv pip install -r requirements.txt

# or with plain pip
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Then add Tesseract (see below) and run:

```powershell
.venv\Scripts\python main.py
```

### Tesseract

EndCall uses [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) to read the number. The repo doesn't include it because it's about 100 MB of binaries. To set it up:

1. Install Tesseract for Windows from the [UB Mannheim builds](https://github.com/UB-Mannheim/tesseract/wiki).
2. Copy the installed `Tesseract-OCR` folder into the project root, so you have `Tesseract-OCR/tesseract.exe` next to `main.py`.

EndCall looks for Tesseract in this order:

1. `Tesseract-OCR/` in the app folder
2. A path you picked with **Locate…**
3. Your `PATH`
4. The default install locations

## Build the .exe

```powershell
uv pip install pyinstaller    # or: pip install pyinstaller
.venv\Scripts\python build.py
```

This creates `dist/EndCall/EndCall.exe` and `dist/EndCall-<version>-windows.zip`. The build includes only the parts of Tesseract that OCR needs (the executable, its DLLs, English data and its license), not the training tools.

Close any running `EndCall.exe` first, since Windows locks its files. To publish a release, upload the zip to a new **GitHub Release**.

To give the .exe your own icon, add `assets/logo.ico`. `assets/logo.png` is used for the window icon and header.

## Project structure

```
EndCall_Autoclicker/
├── main.py                 # entry point
├── build.py                # PyInstaller build + zip
├── requirements.txt
├── assets/                 # logo.png / logo.ico (optional)
├── Tesseract-OCR/          # bundled OCR engine (not in git)
├── endcall/
│   ├── app.py              # main window and its actions
│   ├── monitor.py          # background reading loop
│   ├── trigger.py          # rules for when to end the call
│   ├── ocr.py              # screen capture + number reading
│   ├── region_picker.py    # drag-to-select overlay
│   ├── config.py           # paths, defaults, saved settings
│   └── theme.py            # colors and styled widgets
└── tests/
    ├── test_trigger.py     # rule tests
    ├── test_ocr.py         # reads real captures
    └── fixtures/           # sample captures (count_<number>_*.png)
```

Settings are saved to `config.json` in the project folder when running from source, and to `%APPDATA%\EndCall\config.json` for the built app.

## Tests

```powershell
.venv\Scripts\python -m unittest
```

The reading tests need Tesseract and are skipped without it.

## Limitations

- Windows only.
- Works on the main monitor only.
- The meeting window can't be covered or minimized while monitoring, because EndCall reads what's on screen.
- Reading accuracy depends on how clearly your meeting app shows the number.

## Credits

- OCR by [Tesseract](https://github.com/tesseract-ocr/tesseract) (Apache License 2.0). Its license is included in builds.
- Built with OpenCV, Pillow, PyAutoGUI and Tkinter.
