# Architecture

src-layout package src/ggu_vdod. Entry: root pp.py -> ui/qt/application.py -> QtMainWindow.

| Package | Responsibility |
| --- | --- |
| core | constants, formatting, version (single source of truth) |
| config | paths, atomic settings store, central SettingsManager |
| uth | DPAPI credential store, Windows Credential Manager, Mailpit client |
| download | Qt-free DownloadEngine + structured DownloadJob model |
| conversion | FFmpeg argument builders, post-processors, sidecar cleanup |
| preview | metadata/thumbnail retrieval with bot-check fallbacks |
| services | errors classifier, probe, network, i18n, audio, updates |
| ui | PySide6 window, dialogs, theme, widgets |

Dependencies point inward: UI -> services/engine; core/config never import UI.

Versioning: core/version.py is the single source of truth. Every dev build bumps
PATCH and BUILD together (e.g. v0.2.13 #069). Keep pyproject.toml in sync.
