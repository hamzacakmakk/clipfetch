# ClipFetch

A simple **yt-dlp GUI + CLI** for Windows. Paste multiple links, download them all at once, and get **editor-ready** files — videos are auto-converted to H.264/AAC with a constant frame rate, so they import cleanly into Premiere / DaVinci instead of coming in as "audio only".

Works with Instagram, YouTube, TikTok, X and every site [yt-dlp](https://github.com/yt-dlp/yt-dlp) supports.

---

## Features

- 📋 Multiple links at once (one per line) + **Paste** button
- ⚡ Parallel downloads (1–8 at a time)
- 🎚️ Quality: `best` / `1080` / `720` / `mp3`
- 🎬 **Auto editor-compatibility** — converts av1/vp9/opus **and** variable-frame-rate H.264 to constant-fps H.264/AAC (fixes Premiere `importerMPEG` / "audio only" errors). Already-good files are left untouched.
- 🍪 **cookies.txt** support with a live "Instagram login found" indicator
- 📊 Progress bar + a per-file log of exactly what format change was made
- 🌙 Dark / light mode
- 🌐 English (default) / Türkçe UI
- 🔧 One-click **Setup** that installs/updates yt-dlp and ffmpeg
- 🖥️ Full **CLI** mode for the terminal
- 💾 Remembers all your settings

---

## Requirements

- Windows 10/11
- [Python 3.9+](https://www.python.org/downloads/) — tick **"Add Python to PATH"** during install
- `yt-dlp` and `ffmpeg` are installed automatically by the setup step below

---

## Quick start

```bat
git clone https://github.com/hamzacakmakk/clipfetch.git
cd clipfetch
setup.bat        :: installs yt-dlp + ffmpeg
start.bat        :: launches the GUI
```

Or manually:

```bat
pip install -r requirements.txt
python clipfetch.py --setup     :: installs ffmpeg if missing
python clipfetch.py             :: opens the GUI
```

> On first launch, `yt-dlp` is also auto-installed if it's missing.

---

## GUI usage

1. Paste links (one per line) — or hit **Paste**.
2. Pick a **Quality** (default `best`) and a save folder.
3. For Instagram / private posts, set up **cookies.txt** (see below).
4. Click **Download**.

The **(i) How to use** button inside the app has the full guide. **Setup / Update** installs or refreshes yt-dlp + ffmpeg — use it if a site stops working.

---

## CLI usage

```bat
python clipfetch.py <link1> <link2> ...
python clipfetch.py -f 1080 -o "C:/downloads" <link>
python clipfetch.py --audio <link>                :: mp3 only
python clipfetch.py --cookies cookies.txt <link>  :: Instagram etc.
python clipfetch.py --browser firefox <link>      :: cookies from a browser
python clipfetch.py --archive <link>              :: skip already-downloaded
python clipfetch.py --no-fix <link>               :: keep original codec (no H.264 convert)
python clipfetch.py --setup                        :: install/update dependencies
```

| Option | Meaning |
| --- | --- |
| `-f, --format` | `best` (default), `1080`, `720`, `mp3` |
| `-o, --output` | output folder |
| `--audio` | audio only (mp3) |
| `--cookies` | path to a `cookies.txt` |
| `--browser` | read cookies from a browser (`chrome`, `firefox`, `edge`, ...) |
| `--archive` | skip videos already downloaded |
| `--no-fix` | don't auto-convert to H.264/constant-fps |
| `--setup` | install/update yt-dlp + ffmpeg |

Run with **no arguments** to open the GUI.

---

## Cookies (Instagram / login-required) — important

Instagram won't serve posts to logged-out users, so cookies are required. Chrome/Edge now **encrypt** their cookie database, so reading cookies straight from the browser often fails. The reliable way is a `cookies.txt`:

1. Install the **"Get cookies.txt LOCALLY"** browser extension.
2. **Log in** at `instagram.com`.
3. **While the instagram.com tab is open**, click the extension → **Export** a `cookies.txt`.
4. In the app: **Cookies → cookies.txt file**, then select the file. When it shows green **"Instagram login found"**, you're ready. (CLI: `--cookies cookies.txt`.)

> ⚠️ `cookies.txt` contains your login session — **never share or commit it** (it's in `.gitignore`).

---

## Why videos come out H.264

Web/phone videos are often **av1/vp9** with **opus** audio, or H.264 with a **variable frame rate**. Editors like Premiere either refuse them ("unsupported compression type") or import audio only (`importerMPEG` low-level exception). ClipFetch probes every finished file and, only when needed, re-encodes to **H.264 (High) / AAC / yuv420p / constant fps** — the format editors reliably accept. Files that are already fine are not touched, so there's no needless quality loss or waiting.

Use `--no-fix` (CLI) if you want the raw original stream instead.

---

## Notes

- Preferring H.264 means YouTube **4K/1440p** usually downloads as **1080p** (higher resolutions exist only in av1/vp9, which editors don't accept). Instagram/TikTok are H.264 already.
- Settings are saved to `clipfetch_config.json` (git-ignored).
- Downloading with your account cookies may violate a site's Terms of Service; use responsibly.

---

## License

MIT — see [LICENSE](LICENSE). Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [ffmpeg](https://ffmpeg.org/).
