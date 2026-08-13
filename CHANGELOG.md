# Changelog

All notable changes to GGU_VDOD are documented in this file.

## v0.002.006 (051) - 2026-08-13

### Fixed
- **Video Timestamp Range Cutter**: Fixed time string parser (`parse_time_str_to_seconds`) to handle units like `10s`, `180s`, `1m30s`, `2.5m`, `00:01:30`, and plain numbers.
- **FFmpeg Header Injection for Section Downloads**: Added `external_downloader_args` (`-headers "User-Agent: ...\r\n"`) to prevent YouTube CDN 403 Forbidden errors or code 3436169992 exit crashes when clipping range streams.
- **FFmpeg PATH Environment Resolution**: Prepended permanent FFmpeg directory (`D:\GGU_VDOD\ffmpeg`) to `os.environ["PATH"]` so `yt-dlp`'s `FFmpegFD` section downloader resolves `ffmpeg.exe` instantly.
- **TLS Impersonation Compatibility**: Replaced `curl_cffi` with version `0.15.0` to preserve `yt-dlp` compatibility, and added safe fallback checks for impersonation targets.
- **JS Runtime Warning Silencing**: Filtered out `No supported JavaScript runtime could be found` deprecation warnings from logger box and added automatic discovery for system `node`, `deno`, `bun`, and `quickjs` runtimes.

## v0.002.005 (050) - 2026-08-12

### Added

- Added an in-app button that updates available Python dependencies through the project virtual environment.
- Added a visible rebuild reminder after dependency updates so the packaged EXE stays in sync.
- Applied an application-wide popup policy: custom Qt dialogs now use normal Windows minimize, maximize/restore, resize, and close controls.

## v0.002.004 (049) - 2026-08-11

### Fixed

- Route final download failures from the background worker to visible, classified Qt alerts.
- Preserve the real yt-dlp error in each alert instead of replacing it with a generic queue summary.
- Use distinct sound patterns for error categories, including rate limits, authentication, network, disk, and format failures.
- Recognize Chrome and Edge cookie-database copy failures as a clear browser-cookie issue.
- Correct the download-range availability check used by timestamp trimming.

## v0.001.045 - 2026-08-10

### Added
- Cloudflare HTTP 403 anti-bot challenge bypass via `curl_cffi` Chrome TLS impersonation.
- Automatic DPAPI domain session credential resolution and parameter injection for media downloads.
- 18+ Adult Age Verification gate modal and universal auth setup dialogs.
- Automatic 24-hour component and dependency update check verifying yt-dlp, PySide6, Pillow, PyInstaller, curl_cffi, FFmpeg, and FFprobe.
- Permanent FFmpeg & FFprobe directory integration (`D:\GGU_VDOD\ffmpeg\`).
- Force Application Restart option in Edit menu (`Ctrl+Shift+` `) and process tree termination (`taskkill`).
- Detailed `AboutDialog` with developer info (XerumGG / GG_Uranium), MIT License, and comprehensive use cases.
- Clean rounded ETA formatting (`5m 49s`) and 10-second throttled log stream updates.
- Automated clean build script (`build_exe.ps1`) targeting standard `dist/GGU_VDOD/`.

## 0.1.30-dev.30 - 2026-08-09

### Added

- Native Windows Credential Manager integration (`advapi32.dll CredWriteW/CredReadW/CredDeleteW`) storing encrypted credentials under `GGU_VDOD:<domain>`.
- Dual-cipher security engine combining Windows DPAPI encryption (`CryptProtectData`) and salted PBKDF2 HMAC-SHA256 key derivation.
- PySide6 `AccountSessionWidget` control center tab displaying domain sessions, account labels, real-time TTL expiration countdowns, and session wipers.
- Protected media `SignInPromptDialog` modal prompting for browser session authorization when links require sign-in.
- Local Mailpit REST API client (`http://localhost:8025`) and domain allowlist validator (`localhost`, `*.local`, `*.test`, `*.staging`).
- PySide6 `MailpitTestInboxWidget` tab displaying captured staging verification emails and one-click verification link extraction.
- Automatic temporary cookie wipers and application lifecycle shutdown cleanup hooks in `closeEvent()`.

## 0.1.26-dev.26 - 2026-08-09

### Added

- Consent-first Netscape `cookies.txt` import with local validation and a domain-only summary.
- One-time cookie use by default, with an optional remembered file path that requires confirmation in each app session.

## 0.1.25-dev.25 - 2026-08-09

### Fixed

- Restored Audio mode, output format, and advanced settings from saved preferences.
- Repaired configurable zoom shortcuts, Ctrl + mouse-wheel zoom, and scroll-speed application.
- Restored retry, cookie fallback, subtitle-rate-limit fallback, and format diagnostics in the Qt downloader.
- Added safe audio conversion for every listed audio output target, including OGG, WMA, and AIFF.
- Removed the global TLS certificate-bypass patch.
- Moved format discovery off the UI thread and retained active worker lifetimes during shutdown.

### Changed

- The downloader now tries an exact selected video height before using a lower available fallback.
- Format logs now report selected source streams, fallback resolution, conversion scaling, and final container target.

## 0.2.0-alpha.1 - 2026-08-03

### Changed

- Moved the application implementation into a source-layout package.
- Added modular package boundaries, architecture documentation, and project
  governance documents.

### Notes

- This is a structure-only migration. Existing downloader behavior is retained
  while modules are extracted in follow-up commits.
