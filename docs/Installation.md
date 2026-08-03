# Installation

Download the Windows release archive, extract it, and run `GGU_VDOD.exe`.

FFmpeg is required for merging and conversion. The packaged release searches
for a bundled copy automatically; it can also be selected in Advanced options.

For development, create a virtual environment and install the pinned packages:

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
python app.py
```
