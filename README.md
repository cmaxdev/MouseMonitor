# MMA — Auto input (scroll & Alt+Tab)

Windows tool that **continuously** generates:

- **Mouse scroll** — every **2–5 seconds** (random interval after each scroll)
- **Alt+Tab** — every **5–8 seconds** (random interval); **Tab** is pressed **several times** (2–7) while Alt is held

Uses **Windows `SendInput`** (ctypes). **No user-activity monitoring** — generation runs until you stop the app.

## Quick start

### Executable

1. Open `dist\mma.exe`
2. Press **Ctrl+C** in the console to stop

### Python

```bash
python mma.py
```

No third-party packages needed to run the script (only optional: PyInstaller to build).

## Build executable

```bash
pip install pyinstaller
pyinstaller mma.spec
```

Output: `dist\mma.exe`

See `BUILD_INSTRUCTIONS.md` for more options.

## Requirements

- **Windows** (uses `user32` / `SendInput`)
- Python 3.6+ for running `mma.py` from source

## Disclaimer

This injects synthetic input system-wide. Use only on machines and accounts where you are allowed to do so.
