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
    }
    if (Test-Path "d:\GGU_VDOD\ffmpeg\ffprobe.exe") {
        Copy-Item "d:\GGU_VDOD\ffmpeg\ffprobe.exe" -Destination "$dest_ffmpeg\ffprobe.exe" -Force
    }
    # qjs: prefer the permanent ffmpeg folder, fall back to the tracked bin copy
    $qjs_source = @("d:\GGU_VDOD\ffmpeg\qjs.exe", "d:\GGU_VDOD\bin\qjs.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($qjs_source) {
        Copy-Item $qjs_source -Destination "$dest_ffmpeg\qjs.exe" -Force
    }
    Write-Host "[SUCCESS] Permanent build complete at 'd:\GGU_VDOD\dist\GGU_VDOD\GGU_VDOD.exe'" -ForegroundColor Cyan

    # Remove runtime-generated user data from the staging folder before packaging
    Remove-Item -Recurse -Force "d:\GGU_VDOD\dist\GGU_VDOD\temp_cookies" -ErrorAction SilentlyContinue

    # Compile the Windows installer when Inno Setup is available
    $iscc = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    $app_version = & d:\GGU_VDOD\venv\Scripts\python.exe -c "import sys; sys.path.insert(0, r'd:\GGU_VDOD\src'); from ggu_vdod.core.version import PACKAGE_VERSION; print(PACKAGE_VERSION)"
    if ($iscc) {
        Write-Host "[INFO] Building installer v$app_version with Inno Setup..." -ForegroundColor Green
        & $iscc "/DAppVersion=$app_version" "/DSourceDir=d:\GGU_VDOD\dist\GGU_VDOD" "d:\GGU_VDOD\installer\GGU_VDOD.iss"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[SUCCESS] Installer ready: 'd:\GGU_VDOD\installer_output\GGU_VDOD-setup-v$app_version.exe'" -ForegroundColor Cyan
        } else {
            Write-Host "[ERROR] Inno Setup compilation failed with exit code $LASTEXITCODE" -ForegroundColor Red
        }
    } else {
        Write-Host "[WARN] Inno Setup 6 not found - skipping installer. Install it from https://jrsoftware.org/isdl.php to build GGU_VDOD-setup-*.exe" -ForegroundColor Yellow
    }
} else {
    Write-Host "[ERROR] PyInstaller build failed with exit code $LASTEXITCODE" -ForegroundColor Red
}
# Keep the window open on double-click so results/errors stay visible.
if (-not $env:CI -and -not $env:GGU_NO_PAUSE) {
    Write-Host ""
    Write-Host "[INFO] Build finished. Press Enter to close this window..." -ForegroundColor Gray
    [void](Read-Host)
}
