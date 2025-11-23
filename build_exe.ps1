# PowerShell script to build MMA Mouse Monitor executable
Write-Host "Building MMA Mouse Monitor executable..." -ForegroundColor Green
Write-Host ""

# Check if PyInstaller is installed
try {
    python -c "import PyInstaller" 2>$null
    Write-Host "PyInstaller found." -ForegroundColor Green
} catch {
    Write-Host "PyInstaller not found. Installing..." -ForegroundColor Yellow
    pip install pyinstaller
}

Write-Host ""
Write-Host "Building executable with PyInstaller..." -ForegroundColor Green
Write-Host ""

# Build the executable
pyinstaller --onefile `
    --name "MouseMonitor" `
    --console `
    --hidden-import=pynput `
    --hidden-import=pynput.mouse `
    --hidden-import=pynput.mouse._win32 `
    --hidden-import=ctypes `
    --hidden-import=ctypes.wintypes `
    --collect-all pynput `
    mma.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Build completed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Executable location: dist\MouseMonitor.exe" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "You can now run MouseMonitor.exe without Python installed." -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Read-Host "Press Enter to continue"

