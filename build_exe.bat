@echo off
echo Building MMA Mouse Monitor executable...
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

echo.
echo Building executable with PyInstaller...
echo.

REM Build the executable
pyinstaller --onefile ^
    --name "MouseMonitor" ^
    --icon=NONE ^
    --console ^
    --add-data "README.md;." ^
    --hidden-import=pynput ^
    --hidden-import=pynput.mouse ^
    --hidden-import=pynput.mouse._win32 ^
    --hidden-import=ctypes ^
    --hidden-import=ctypes.wintypes ^
    --collect-all pynput ^
    mma.py

if errorlevel 1 (
    echo.
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build completed successfully!
echo.
echo Executable location: dist\MouseMonitor.exe
echo.
echo You can now run MouseMonitor.exe without Python installed.
echo ========================================
echo.
pause

