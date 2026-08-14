# GGU_VDOD Permanent Build Script
# Always builds into standard 'dist/GGU_VDOD' folder

Write-Host "[INFO] Terminating active GGU_VDOD / FFmpeg processes..." -ForegroundColor Cyan
taskkill /F /IM GGU_VDOD.exe /T 2>$null
taskkill /F /IM ffmpeg.exe /T 2>$null
taskkill /F /IM ffprobe.exe /T 2>$null
Start-Sleep -Seconds 1

# Clean temporary folders
Write-Host "[INFO] Cleaning temporary build folders..." -ForegroundColor Cyan
Get-ChildItem -Path "d:\GGU_VDOD" -Filter "dist_v*" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path "d:\GGU_VDOD" -Filter "dist_old_*" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
if (Test-Path "d:\GGU_VDOD\build") { Remove-Item -Recurse -Force "d:\GGU_VDOD\build" -ErrorAction SilentlyContinue }

# Execute PyInstaller into standard dist directory
Write-Host "[INFO] Running PyInstaller into permanent 'dist' directory..." -ForegroundColor Green
.\venv\Scripts\pyinstaller --noconsole --paths src --add-data "src/ggu_vdod/locales;ggu_vdod/locales" --collect-all PySide6 --name GGU_VDOD --clean -y app.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "[INFO] PyInstaller build succeeded! Bundling FFmpeg & FFprobe..." -ForegroundColor Green
    $dest_ffmpeg = "d:\GGU_VDOD\dist\GGU_VDOD\ffmpeg"
    New-Item -ItemType Directory -Force -Path $dest_ffmpeg | Out-Null
    
    if (Test-Path "d:\GGU_VDOD\ffmpeg\ffmpeg.exe") {
        Copy-Item "d:\GGU_VDOD\ffmpeg\ffmpeg.exe" -Destination "$dest_ffmpeg\ffmpeg.exe" -Force
        Copy-Item "d:\GGU_VDOD\ffmpeg\ffmpeg.exe" -Destination "d:\GGU_VDOD\dist\GGU_VDOD\ffmpeg.exe" -Force
    }
    if (Test-Path "d:\GGU_VDOD\ffmpeg\ffprobe.exe") {
        Copy-Item "d:\GGU_VDOD\ffmpeg\ffprobe.exe" -Destination "$dest_ffmpeg\ffprobe.exe" -Force
        Copy-Item "d:\GGU_VDOD\ffmpeg\ffprobe.exe" -Destination "d:\GGU_VDOD\dist\GGU_VDOD\ffprobe.exe" -Force
    }
    Write-Host "[SUCCESS] Permanent build complete at 'd:\GGU_VDOD\dist\GGU_VDOD\GGU_VDOD.exe'" -ForegroundColor Cyan
} else {
    Write-Host "[ERROR] PyInstaller build failed with exit code $LASTEXITCODE" -ForegroundColor Red
}
