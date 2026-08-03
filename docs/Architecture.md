# Architecture

GGU_VDOD uses a source-layout package under `src/ggu_vdod`.

`app.py` at the repository root is only a compatibility launcher for the
Windows build. `src/ggu_vdod/app.py` is the composition root.

## Migration status

The previous single-file implementation is preserved at
`src/ggu_vdod/ui/main_window.py` as a behavior-preserving baseline. It will be
split incrementally; no downloader behavior is intentionally changed in this
structural migration.

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
