# Architecture

GGU_VDOD uses a source-layout package under `src/ggu_vdod`.

`app.py` at the repository root is only a compatibility launcher for the
Windows build. `src/ggu_vdod/app.py` is the composition root.

## Migration status

The previous single-file implementation is preserved at
`src/ggu_vdod/ui/main_window.py` as a behavior-preserving baseline. The first
extraction pass is complete; no downloader behavior is intentionally changed
in this structural migration.

The current extracted responsibilities are:

- `core/constants.py` — quality, format, retry, zoom, and layout constants.
- `core/formatting.py` — byte and transfer-rate formatting.
- `config/paths.py` and `config/store.py` — application locations and settings persistence.
- `conversion/options.py` — codec arguments, output templates, and sidecar cleanup.
- `conversion/postprocessor.py` — the local FFmpeg postprocessor adapter.
- `preview/metadata.py` — YouTube URL normalization and thumbnail/source metadata helpers.
- `services/ffmpeg.py` and `services/network.py` — FFmpeg discovery and connectivity/error helpers.
- `ui/widgets.py` — reusable undo/redo entry and animated tooltip widgets.

The remaining UI composition, preview orchestration, update dialogs, and
download orchestration stay together temporarily because they share Tk state.
They are the next extraction targets after this baseline has been reviewed.

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
