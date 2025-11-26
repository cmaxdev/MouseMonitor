# Building Executable File

This guide explains how to build the Mouse Monitor application into a standalone executable that runs without Python.

## Prerequisites

- Python 3.6 or higher installed
- pip (Python package manager)

## Quick Build (Windows)

### Option 1: Using Batch Script (Recommended)

Simply double-click `build_exe.bat` or run in Command Prompt:
```batch
build_exe.bat
```

### Option 2: Using PowerShell Script

Run in PowerShell:
```powershell
.\build_exe.ps1
```

### Option 3: Manual Build

1. Install PyInstaller:
```bash
pip install pyinstaller
```

2. Build the executable:
```bash
pyinstaller --onefile --name mma --console --hidden-import=pynput --hidden-import=pynput.mouse --hidden-import=pynput.mouse._win32 --collect-all pynput mma.py
```

## Build Output

After building, you'll find:
- **Executable**: `dist\mma.exe`
- **Build files**: `build\` folder (can be deleted after building)
- **Spec file**: `mma.spec` (can be kept for future builds)

## Running the Executable

1. Navigate to the `dist` folder
2. Run `mma.exe`
3. No Python installation required!

## Distribution

To distribute the application:
1. Copy `dist\mma.exe` to the target computer
2. The executable is completely standalone - no dependencies needed
3. You can also distribute the `README.md` file with usage instructions

## Troubleshooting

### Antivirus Warning
Some antivirus software may flag PyInstaller executables as suspicious. This is a false positive. You can:
- Add an exception for the executable
- Submit to your antivirus vendor as a false positive
- Use Windows Defender or another trusted scanner

### Missing Dependencies
If the executable fails to run, try rebuilding with:
```bash
pyinstaller --onefile --name mma --console --collect-all pynput --collect-all ctypes mma.py
```

### File Size
The executable will be relatively large (20-30MB) because it includes Python and all dependencies. This is normal for PyInstaller one-file builds.

## Advanced: Customizing the Build

Edit `mma.spec` (generated after first build) for advanced options like:
- Adding an icon
- Including additional files
- Customizing the build process

Then rebuild with:
```bash
pyinstaller mma.spec
```

