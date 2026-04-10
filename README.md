# Mouse Painter 🎨

> Record your mouse journey — watch it turn into glowing art.

Mouse Painter tracks your mouse movements and clicks in the background, then renders them into a beautiful neon-glow artwork saved directly to your Desktop.

![Mouse Painter Demo](https://img.shields.io/badge/Python-3.9%2B-blue?style=flat-square&logo=python) ![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-lightgrey?style=flat-square) ![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## What it looks like

Each session produces a unique image like this:

- **Glowing neon path** — your full mouse trail, colored across the rainbow spectrum from start to finish
- **Click markers** — blue halos for left clicks, orange for right clicks
- **Start / End diamonds** — green marks where you began, red where you stopped
- **Stats overlay** — duration, total distance, point count, and click summary

---

## Features

- One-click recording — window minimizes automatically so you can work normally
- Tracks every mouse position and click in the background
- Generates a full-screen PNG artwork saved to your Desktop
- Auto-opens the finished image when done
- Minimal, dark UI — stays out of your way

---

## Requirements

- Python 3.9+
- [pynput](https://pypi.org/project/pynput/)
- [Pillow](https://pypi.org/project/Pillow/)

Install dependencies:

```bash
pip install pynput Pillow
```

---

## Run from source

```bash
python main.py
```

> **macOS:** On first run, grant Accessibility access when prompted:
> System Settings → Privacy & Security → Accessibility → enable Mouse Painter

---

## Build a standalone app

### macOS

```bash
bash build_app.sh
```

Produces `dist/MousePainter` — a self-contained app, no Python needed.

If macOS blocks it on first open: **System Settings → Privacy & Security → Open Anyway**

### Windows

```bat
build_app_windows.bat
```

Produces `dist\MousePainter.exe` — ready to share and run anywhere.

---

## How it works

1. Press **Start Recording** — the window minimizes, tracking begins
2. Use your computer normally — browse, work, doodle with your mouse
3. Press **Stop & Paint** — Mouse Painter renders your session into art
4. The PNG is saved to your Desktop and opened automatically

---

## Project structure

```
mouse-painter/
├── main.py                  # App logic, UI, and image generation
├── build_app.sh             # macOS build script (PyInstaller)
├── build_app_windows.bat    # Windows build script (PyInstaller)
└── index.html               # (Optional) web landing page
```

---

## License

MIT — do whatever you want with it.
