@echo off
echo Building MMA executable...
echo.

python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

echo.
pyinstaller mma.spec

if errorlevel 1 (
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo Done: dist\mma.exe
pause
