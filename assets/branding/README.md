# Branding Assets — put files here

| File | Used for | Specs |
|---|---|---|
| `icon.ico` | App exe + installer icon | 256/128/64/48/32/16 px multi-size ICO |
| `logo.png` | README header + About dialog | 512x512 or 1024x1024 PNG, transparent |
| `banner.png` | GitHub social preview (Settings > Social preview) | 1280x640 PNG |
| `demo.mp4` or `demo.gif` | README demo section (optional) | < 10 MB, 15-30 s screen capture |

Once `icon.ico` exists here, wire it in two places:

1. `GGU_VDOD.spec` / build command: add `--icon assets\branding\icon.ico`
2. `installer\GGU_VDOD.iss`: add lines
   ```
   SetupIconFile=..\assets\branding\icon.ico
   UninstallDisplayIcon={app}\GGU_VDOD.exe
   ```

GitHub repo Settings → General → Social preview: upload `banner.png`.
