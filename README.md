# GGU_VDOD

Fast, free desktop media downloader & converter for Windows.
Paste links from YouTube, social platforms, streaming sites — download video or audio in any format.

- **Install:** download `GGU_VDOD-setup-vX.Y.Z.exe` from [Releases](../../releases/latest) → run it. No admin needed.
- **Portable:** grab `GGU_VDOD-windows-portable.zip`, extract, run.
- **Update:** click **Check for Updates** inside the app (top-right) or just download the new setup.

| | |
|---|---|
| **Developer** | XerumGG |
| **Stack** | Python · PySide6 · yt-dlp · FFmpeg |
| **License** | MIT |

## Features

- 4K/1080p video, MP3/FLAC/WAV audio, playlists, batch paste
- Format conversion via bundled FFmpeg (MP4, MKV, WEBM, MP3, OPUS, ...)
- Browser-cookie import for member-only content
- Account session manager (DPAPI encrypted), local test inbox
- Duplicate detection, error explanations in plain language
- 11 languages, dark themes, custom fonts and zoom

## Build from source

```powershell
pip install -r requirements.txt pyinstaller
.\build_exe.ps1
```

Output: `dist\GGU_VDOD\`. Installer requires [Inno Setup 6](https://jrsoftware.org/isdl.php).
