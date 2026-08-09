# Changelog

All notable changes to GGU_VDOD are documented in this file.

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
