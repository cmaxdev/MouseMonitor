# Build MMA using mma.spec (no pynput dependency)
Write-Host "Building MMA executable..." -ForegroundColor Green
try {
    python -c "import PyInstaller" 2>$null
} catch {
    pip install pyinstaller
}
pyinstaller mma.spec
if ($LASTEXITCODE -eq 0) {
    Write-Host "Done: dist\mma.exe" -ForegroundColor Green
} else {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}
