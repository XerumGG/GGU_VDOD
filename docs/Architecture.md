# Architecture

GGU_VDOD uses a source-layout package under `src/ggu_vdod`.

`app.py` at the repository root is only a compatibility launcher for the
Windows build. `src/ggu_vdod/app.py` is the composition root.

## Migration status

The previous single-file implementation is preserved at
`src/ggu_vdod/ui/main_window.py` as a legacy reference. The active application
uses the PySide6 window in `src/ggu_vdod/ui/qt/main_window.py`.

The current extracted responsibilities are:

- `core/constants.py` — quality, format, retry, zoom, and layout constants.
- `core/formatting.py` — byte and transfer-rate formatting.
- `config/paths.py` and `config/store.py` — application locations and settings persistence.
- `conversion/options.py` — codec arguments, output templates, and sidecar cleanup.
- `conversion/postprocessor.py` — the local FFmpeg postprocessor adapter.
- `preview/metadata.py` and `preview/service.py` — preview URL normalization,
  public metadata fallback, and extractor-backed title/source/thumbnail retrieval.
- `services/ffmpeg.py` and `services/network.py` — FFmpeg discovery and connectivity/error helpers.
- `ui/widgets.py` — reusable undo/redo entry and animated tooltip widgets.

The remaining UI composition, preview orchestration, update dialogs, and
download orchestration stay together temporarily because they share Tk state.
They are the next extraction targets after this baseline has been reviewed.

## Qt migration status

The active desktop UI lives in `src/ggu_vdod/ui/qt`. It uses PySide6 and owns
window composition, preferences, previews, and downloader orchestration. The
legacy Tk/ttkbootstrap window remains only as a reference during cleanup.

| Qt module | Responsibility |
| --- | --- |
| `application.py` | QApplication startup and process-wide setup |
| `theme.py` | Qt palette and stylesheet |
| `widgets.py` | reusable Qt controls, including transfer status |
| `main_window.py` | window composition and UI-only interactions |

This parallel approach lets the working legacy UI remain available while Qt
controllers replace the Tk-bound workflow one responsibility at a time.

## Intended module ownership

| Package | Responsibility |
| --- | --- |
| `core` | models, errors, events, constants |
| `config` | defaults, paths, validation, user preferences |
| `download` | queueing, yt-dlp adapter, progress, format selection |
| `conversion` | FFmpeg and media naming |
| `preview` | title, source, and thumbnail retrieval |
| `plugins` | optional source/output/post-processing extensions |
| `services` | logging, updates, system integration |
| `ui` | windows, dialogs, panels, themes, widgets |

Dependencies point inward: UI calls services and application adapters; core
code never imports UI code.

## Development build versioning

`core/version.py` is the single source of truth for the development label shown
at the bottom-right of both desktop interfaces. Its format is
`Development build : vMajor.Minor.Patch (Build)` with the minor, patch, and
build values zero-padded to three digits. Increase the relevant value by `001`
for each future change set.
