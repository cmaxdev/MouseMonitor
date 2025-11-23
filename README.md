# Mouse Monitor and Auto-Mover

A Python application that monitors mouse movement and automatically moves the mouse if it remains idle for more than 30 seconds.

## Features

- **Checks mouse position every 5 seconds** to detect inactivity
- **Automatically moves the mouse** with random distances every 5 seconds if no movement detected for 20 seconds
- **Stops automatic movement** immediately when real mouse movement is detected
- **Uses Windows API** to generate proper input events detectable by time tracking software (like ManicTime)
- Thread-safe implementation with real-time mouse event monitoring
- **Standalone executable** - No Python installation required!

## Quick Start (Executable)

### Option 1: Use Pre-built Executable

1. Go to the `dist` folder
2. Double-click `MouseMonitor.exe`
3. That's it! No Python required.

### Option 2: Build Your Own Executable

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Build the executable:
   - **Windows Batch**: Double-click `build_exe.bat`
   - **PowerShell**: Run `.\build_exe.ps1`
   - **Manual**: See `BUILD_INSTRUCTIONS.md`

3. Find your executable in `dist\MouseMonitor.exe`

## Installation (Python Script)

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Running the Executable

Simply double-click `MouseMonitor.exe` from the `dist` folder, or run from command line:
```bash
dist\MouseMonitor.exe
```

### Running the Python Script

```bash
python mma.py
```

The application will:
- Monitor mouse movements in real-time
- Check mouse activity every 5 seconds (configurable)
- Start auto-moving the mouse with random distances if idle for 20 seconds (configurable)
- Stop auto-moving when you move the mouse
- Generate proper Windows input events that time tracking software can detect

Press `Ctrl+C` to stop the application.

## Requirements

### For Executable:
- **Windows 10/11** (64-bit)
- **No Python required!** The executable is completely standalone

### For Python Script:
- Python 3.6+
- pynput library

## How it works

1. The application listens for mouse movement events in real-time using `pynput`
2. Every 5 seconds, it checks if the mouse has been idle for 20 seconds
3. If idle for 20+ seconds, it starts automatically moving the mouse with **random distances** (100-600 pixels) in random directions every 5 seconds
4. Uses **Windows API SendInput** to generate proper low-level input events that applications like ManicTime can detect
5. When real mouse movement is detected, it immediately stops the automatic movement
6. Movements are smooth and natural with acceleration/deceleration curves

## Technical Details

- **Low-level Windows API**: Uses `SendInput` with `MOUSEEVENTF_MOVE` flag to generate proper WM_MOUSEMOVE messages
- **Event Detection**: Applications that monitor mouse activity (like ManicTime) will detect these movements
- **Random Movements**: Each movement uses random distance (100-600px) and random direction for natural behavior
- **Smooth Motion**: Implements ease-in-out curves with variable speed for human-like movement
- **Thread-safe**: Uses proper locking mechanisms to prevent race conditions

## Configuration

You can modify these settings in `mma.py`:
- `check_interval`: How often to check mouse activity (default: 5 seconds)
- `idle_threshold`: Time before auto-movement starts (default: 20 seconds)
- `auto_move_interval`: Time between automatic movements (default: 5 seconds)
- `min_distance` / `max_distance`: Random movement distance range (default: 100-600 pixels)

## Notes

- The automatic mouse movements use random distances and directions to appear natural
- The application uses threading to handle monitoring and auto-movement simultaneously
- Safe to run in the background while working
- Works with time tracking software like ManicTime by generating proper Windows input events
- **File Size**: The executable is ~8-9 MB (includes Python runtime and all dependencies)

## Building the Executable

See `BUILD_INSTRUCTIONS.md` for detailed instructions on building your own executable.

