 # GGU_VDOD (cross-platform desktop app)
__Put the link ; Get the VDO, download the MP3, yo yo yo...__


A dark-themed desktop app: paste a video link, pick MP4 (video) or MP3 (audio), click
__Download__. If your internet drops mid-download, it automatically waits, reconnects, and
__resumes from where it stopped__ instead of starting over.

The source runs on Windows, macOS, and Linux. Native packaged executables must be built
on the target operating system with PyInstaller. The Windows build produces
`GGU_VDOD.exe`; macOS/Linux builds produce a native executable for those platforms.

---

## 1. One-time setup (about 5 minutes)

**a) Install Python** (skip if you already have Python 3.9+)
- Download from https://www.python.org/downloads/
- During install, **check the box "Add python.exe to PATH"**

**b) Install ffmpeg** (required - used to merge video/audio and create MP3s)

You have two options - pick whichever is easier:

- Option 1 (recommended, zero-config): bundle it. Download ffmpeg from
  https://www.gyan.dev/ffmpeg/builds/ (get the "essentials" zip), and put
  the ffmpeg executable in a folder named `ffmpeg` next to the built app. On Windows,
  the layout is:
  ```
  dist\GGU_VDOD.exe
  dist\ffmpeg\ffmpeg.exe
  ```
  The app automatically finds it there on startup - **no path to type in, no PATH
  editing.** This is the default the app looks for first.

- **Option 2: install it system-wide.** Open Command Prompt and run:
  ```
  winget install ffmpeg
  ```
  The app also auto-detects ffmpeg if it's already on your system PATH, or installed at
  common locations like `C:\ffmpeg\bin\ffmpeg.exe`. On macOS, Homebrew can install it
  with `brew install ffmpeg`; on Linux use your distribution's package manager.

If ffmpeg is unavailable, the app can still attempt a single-file video download when
the site exposes one, but MP3 conversion and separate video/audio merging require ffmpeg.

Either way, the **"ffmpeg location"** field in the app will show a green
"✓ Using: ..." once it finds one, or a "⚠ not found" note if it can't - at which point
you can just click Browse and point it at your `ffmpeg.exe` manually.

## 2. Build the app

### Windows

1. Put the project files in one folder.
2. Double-click **`build.bat`**.
3. Wait for it to finish - it creates a virtual environment, installs `yt-dlp` and
   `PyInstaller`, then builds the app.
4. Your Windows app is now at:
   ```
   dist\GGU_VDOD.exe
   ```
   Copy that one file (and optionally the `ffmpeg` folder next to it, see above) wherever
   you like - Desktop, a USB drive, etc. It runs standalone.

The default one-file build is convenient to distribute. If Windows security software
flags it, build an unpacked folder instead with `set GGU_BUILD_MODE=onedir` before running
`build.bat`; unpacked PyInstaller builds are often easier for security tools to inspect.

### macOS/Linux

Run `chmod +x build.sh && ./build.sh`. The app will be created in `dist/GGU_VDOD`.
For an unpacked build, use `GGU_BUILD_MODE=onedir ./build.sh`.

You only need to repeat the build if you change `app.py` or want to update `yt-dlp`.

## 3. Using the app

1. The window opens at 1920x1080 (or your full screen if smaller), centered, and resizable.
2. Paste one or more video links into the box (one per line).
3. Choose **Video (MP4)** or **Audio only (MP3)**, and pick a quality.
4. Optionally choose browser cookies or a `cookies.txt` file for sign-in-gated content,
   configure subtitles, metadata, thumbnails, a proxy, live-stream capture, or an exact
   format ID.
5. Check **"Save to"** - it defaults to an app folder inside your user Downloads folder,
   change it if you like.
6. Click **Download**. Progress and any errors show up in the log at the bottom.
7. Click **Open Save Folder** any time to jump straight to your files.

Your last-used save folder and ffmpeg path are remembered automatically for next time.

### If your internet drops mid-download

You don't need to do anything. The app:
- Detects the connection loss (either a network error from the download itself, or a
  direct connectivity check).
- Shows **"Internet connection lost - waiting to resume..."** in the status bar.
- Keeps checking every few seconds in the background.
- The moment your connection is back, it automatically resumes the **same file** using
  yt-dlp's partial-file support (`.part` files) - it picks up from the byte it stopped
  at, it does not redownload from 0%.

You can also click **Cancel** at any point - whatever's been downloaded so far is kept,
and clicking **Download** again later with the same link will resume it rather than
restart it.

## 4. Updating yt-dlp later

YouTube changes things occasionally, which can break downloads until `yt-dlp` is updated.
Use **Check yt-dlp updates** in the app to see whether a newer version is available. If
downloads suddenly start failing, update the development environment:
```
venv\Scripts\activate
pip install --upgrade yt-dlp
```
Then rebuild with `build.bat` on Windows or `build.sh` on macOS/Linux.

## What changed in this version

- **Renamed** to **GGU_VDOD** throughout (window title, built app name).
- **Cross-platform runtime**: Windows, macOS, and Linux use native config folders,
  download defaults, ffmpeg discovery, and folder-opening behavior.
- **Animated tooltips**: hover over guidance text, controls, paths, and options to see a
  short plain-English explanation with a smooth fade-in/fade-out popup.
- **Scrollable interface and context menus**: the main panel supports mouse-wheel
  scrolling, and text fields provide right-click Cut, Copy, Paste, and Select all actions.
- **Transfer status bar**: a fixed qBittorrent-style footer shows download rate, upload
  rate, progress, transferred bytes, ETA, and queue status. Upload remains `0 B/s` because
  this is a download-only application.
- **Authentication support**: browser cookies and `cookies.txt` can be supplied for
  content the user is authorized to access.
- **Subtitles and media metadata**: subtitle downloads/embedding plus optional metadata
  and thumbnail embedding are available.
- **Format inspection**: use **List formats** to inspect the formats yt-dlp reports for a
  URL, then enter an exact format expression such as `137+140` when needed.
- **Playlist visibility and proxy support**: playlist items are logged individually, and
  an HTTP/SOCKS proxy can be configured per user.
- **Live-stream capture**: live URLs can be handed to yt-dlp while broadcasting, with an
  option to request capture from the beginning when the service provides that stream.
- **Dark mode**: the whole interface, including the log panel, dropdowns, and progress
  bar, now uses a dark color scheme. On Windows 10/11 the title bar goes dark too.
- **ffmpeg auto-detected by default**: the field pre-fills itself on startup (checks your
  system PATH, a bundled `ffmpeg` folder next to the exe, and common install locations)
  instead of starting blank.
- **Log panel fixed**: download progress and status updates from the background download
  thread previously could occasionally fail to reach the on-screen log. They're now routed
  through a proper thread-safe queue that the UI polls, and any unexpected error is written
  straight into the log instead of disappearing silently - so if something ever does go
  wrong, you'll see it there rather than a blank panel.

## A note on legal use

Downloading YouTube videos can conflict with YouTube's Terms of Service depending on
the content and what you do with it. This tool is meant for content you own, have
explicit permission to save, or that's licensed for reuse (e.g. Creative Commons) -
please make sure you have the right to download whatever you use it on.
