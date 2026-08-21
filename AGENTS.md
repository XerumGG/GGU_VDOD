# AGENTS.md

## Versioning (required)

`src/ggu_vdod/core/version.py` is the single source of truth. Format:
`Major.Minor.Patch #Build`.

- **Every dev build: `BUILD += 1` AND `PATCH += 1`** (e.g. v0.2.8 #064 →
  v0.2.9 #065). They always move together.
- Feature milestones may bump `MINOR` instead (then `PATCH`/`BUILD` reset).
- Keep `pyproject.toml` `version` in sync:
  `f"{MAJOR}.{MINOR}.{PATCH}.dev{BUILD}"`.

## Build

Rebuild the executable after code changes:

```powershell
.\build_exe.ps1
```

Output lands in `dist\GGU_VDOD\GGU_VDOD.exe`. FFmpeg/FFprobe/qjs are copied in
by the script automatically.
