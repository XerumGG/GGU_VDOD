# Changelog

All notable changes to GGU_VDOD are documented in this file.

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
