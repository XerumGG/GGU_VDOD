# FAQ

**YouTube download fails with 403 Forbidden?**
That's YouTube's bot-check, not your internet. Click Retry (the app auto-retries with alternate clients), or set Advanced > Browser cookies to your browser. Pasting the plain `watch?v=...` link without `&list=...` also helps.

**Download says sign-in / bot verification?**
Pick your browser under Advanced > Browser cookies, or add a session in the Account & Sessions tab. The app also auto-retries with alternate YouTube clients first.

**Can it download Netflix / Spotify / DRM content?**
No — DRM-protected streams can't be downloaded by any app legally.

**Where do files go?**
Your chosen Save folder (default: Downloads\\GGU_VDOD).

**Which sites work?**
1,700+ via yt-dlp: YouTube, TikTok, Instagram, X, Facebook, Reddit, Twitch, Vimeo, SoundCloud, adult tubes, direct MP4/HLS links, and more. Full list: [README](../README.md#where-it-downloads-from).

**Is it free?** Yes - MIT license.

**Antivirus flags the exe?** False positive from PyInstaller; build from source or verify via GitHub Actions logs.
