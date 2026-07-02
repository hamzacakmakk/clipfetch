# -*- coding: utf-8 -*-
"""
ClipFetch - yt-dlp GUI
Paste multiple links, download them all at once.
Instagram / YouTube / TikTok / X and every site yt-dlp supports.
"""

import os
import sys
import glob
import json
import queue
import threading
import zipfile
import argparse
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "clipfetch_config.json")


def _pip_install(*pkgs):
    flags = 0x08000000 if os.name == "nt" else 0
    return subprocess.run([sys.executable, "-m", "pip", "install", "-U", *pkgs],
                          creationflags=flags)


# yt-dlp is required -> auto-install on first run if missing (fresh GitHub clone)
try:
    import yt_dlp
except ImportError:
    _pip_install("yt-dlp")
    import yt_dlp
from yt_dlp.postprocessor import PostProcessor


# ---------------------------------------------------------------------------
# Help texts
# ---------------------------------------------------------------------------
HELP_TR = """CLIPFETCH - NASIL KULLANILIR

1) LINK EKLEME
   - Linkleri alt alta yapistir (her satira bir tane).
   - "Yapistir" butonu panodaki linki listeye ekler.
   - Instagram, YouTube, TikTok, X ve yt-dlp'nin destekledigi tum siteler.

2) KALITE
   - best : en iyi kalite (H.264 tercih edilir)
   - 1080 / 720 : cozunurluk siniri
   - mp3 : sadece ses
   Videolar otomatik olarak H.264/AAC + SABIT kare hizina cevrilir. Boylece
   video duzenleme programlarinda (Premiere, DaVinci vb.) sorunsuz acilir.
   Zaten uygun olan dosyalara dokunulmaz (hizli, kayipsiz).

3) COOKIE (Instagram / giris gerektiren icerik)
   Instagram girissiz acilmadigi icin cerez gerekir.
   Chrome/Edge cerezleri artik sifreledigi icin "Tarayici" secenegi
   calismayabilir. EN SAGLAM YOL = cookies.txt:
     1. Tarayiciya "Get cookies.txt LOCALLY" eklentisini kur.
     2. instagram.com'a GIRIS YAP.
     3. instagram.com sekmesi ACIKKEN eklentiden Export ile cookies.txt kaydet.
     4. Uygulamada: Cerez -> "cookies.txt dosyasi" sec, dosyayi goster.
   Yesil "Instagram girisi var" yazarsa hazirsin.
   NOT: cookies.txt icinde giris bilgin vardir; kimseyle paylasma.

4) AYNI ANDA
   Kac videonun ayni anda inecegini belirler (1-8).

5) KURULUM / GUNCELLE
   Ilk kez kullaniyorsan ya da siteler bozulursa bu butona bas:
   yt-dlp'yi gunceller ve ffmpeg'i (birlestirme/donusturme icin) kurar.

TERMINALDEN (KOMUT SATIRI) KULLANIM
   python clipfetch.py <link1> <link2> ...
   python clipfetch.py -f 1080 -o "C:/indirilenler" <link>
   python clipfetch.py --audio <link>              (sadece mp3)
   python clipfetch.py --cookies cookies.txt <link>
   python clipfetch.py --browser firefox <link>
   python clipfetch.py --setup                     (bagimliliklari kur)
   Argumansiz calistirinca arayuz (GUI) acilir.
"""

HELP_EN = """CLIPFETCH - HOW TO USE

1) ADDING LINKS
   - Paste links one per line.
   - The "Paste" button adds the clipboard link to the list.
   - Instagram, YouTube, TikTok, X and every site yt-dlp supports.

2) QUALITY
   - best : best quality (H.264 preferred)
   - 1080 / 720 : resolution cap
   - mp3 : audio only
   Videos are auto-converted to H.264/AAC + CONSTANT frame rate, so they
   import cleanly into video editors (Premiere, DaVinci, etc.). Files that are
   already fine are left untouched (fast, lossless).

3) COOKIES (Instagram / login-required content)
   Instagram won't open without login, so cookies are required.
   Chrome/Edge now encrypt cookies, so the "Browser" option may fail.
   MOST RELIABLE = cookies.txt:
     1. Install the "Get cookies.txt LOCALLY" browser extension.
     2. LOG IN at instagram.com.
     3. WHILE the instagram.com tab is open, Export a cookies.txt.
     4. In the app: Cookies -> "cookies.txt file", pick the file.
   When it shows green "Instagram login found" you are ready.
   NOTE: cookies.txt contains your login; never share it.

4) AT ONCE
   How many videos download simultaneously (1-8).

5) SETUP / UPDATE
   First run, or when sites break, click this button:
   it updates yt-dlp and installs ffmpeg (needed to merge/convert).

TERMINAL (CLI) USAGE
   python clipfetch.py <link1> <link2> ...
   python clipfetch.py -f 1080 -o "C:/downloads" <link>
   python clipfetch.py --audio <link>              (mp3 only)
   python clipfetch.py --cookies cookies.txt <link>
   python clipfetch.py --browser firefox <link>
   python clipfetch.py --setup                     (install dependencies)
   Run with no arguments to open the GUI.
"""


# ---------------------------------------------------------------------------
# Language strings
# ---------------------------------------------------------------------------
STR = {
    "en": {
        "title": "ClipFetch",
        "links": "Links (one per line):",
        "paste": "Paste",
        "outdir": "Save folder:",
        "browse": "Browse...",
        "format": "Quality:",
        "conc": "At once:",
        "notify": "Notify when done",
        "archive": "Skip already downloaded",
        "cookies": "Cookies:",
        "cookie_opts": ["None", "Browser", "cookies.txt file"],
        "cookiefile": "cookies.txt:",
        "pickfile": "Choose file...",
        "cf_ok": "✔ Instagram login found",
        "cf_nologin": "✗ No Instagram login (re-export on instagram.com)",
        "cf_none": "✗ no file selected",
        "lang": "Language:",
        "dark": "Dark mode",
        "download": "Download",
        "openfolder": "Open Folder",
        "clear": "Clear",
        "howto": "(i) How to use",
        "setup": "Setup / Update",
        "help_title": "How to use",
        "help_text": HELP_EN,
        "status_label": "Status:",
        "ready": "Ready.",
        "ffmpeg_ok": "ffmpeg found.",
        "ffmpeg_warn": "WARNING: ffmpeg not found, audio/video may stay separate.",
        "warn": "Warning",
        "info": "Info",
        "no_links": "Enter at least one link.",
        "need_cookiefile": "Select a valid cookies.txt file.",
        "folder_not_yet": "Folder not created yet.",
        "clip_empty": "Clipboard is empty or not text.",
        "started": "--- Download started for {n} link(s) ---",
        "starting": "starting",
        "merging": "merging/done",
        "pp_already": "{v}/{a}, constant fps -> no conversion needed",
        "pp_recoding": "{v}/{a} -> converting to H.264/AAC (constant fps)...",
        "pp_done": "converted -> H.264/AAC (constant fps)",
        "pp_fail": "conversion FAILED, kept as {v}/{a}",
        "ok": "OK",
        "error": "ERROR",
        "finished_all": "--- All done ---",
        "progress": "Progress: {d}/{t} done",
        "done": "Done: {d}/{t}",
        "notify_title": "Downloads finished",
        "notify_msg": "{d}/{t} downloads completed.",
        "setup_running": "Setup: installing/updating yt-dlp and ffmpeg... this can take a minute.",
        "setup_ok": "Setup complete: yt-dlp updated, ffmpeg ready. Restart to be safe.",
        "setup_ffmpeg_fail": "yt-dlp updated, but ffmpeg could not be installed. See 'How to use'.",
        "hint_chrome_enc": "Chrome/Edge encrypts cookies (v127+) and yt-dlp cannot decrypt them. Use a cookies.txt file instead (Cookies -> cookies.txt file) - it works even while the browser is open. Export it with the 'Get cookies.txt LOCALLY' extension.",
        "hint_browser_open": "{b} is OPEN, so its cookies are locked. Close {b} completely, or use a cookies.txt file (recommended - works even while the browser is open).",
        "hint_cookiefile": "Could not read the cookies.txt file. Pick a valid file exported from your browser.",
        "hint_login": "This post needs login. Set Cookies to Browser (and close that browser) or to a cookies.txt file.",
        "preflight_title": "Browser is open",
        "preflight_msg": "{b} is open, so cookies cannot be read and downloads will fail.\n\nClose {b} completely and try again, or switch Cookies to 'cookies.txt file'.\n\nContinue anyway?",
        "ig_title": "No Instagram login",
        "ig_no_login": "Your cookies.txt has no Instagram login (the 'sessionid' cookie is missing), so Instagram links will fail.\n\nIn your browser: open instagram.com, make sure you are logged in, then export cookies.txt again WHILE the instagram.com tab is open.\n\nContinue anyway?",
    },
    "tr": {
        "title": "ClipFetch",
        "links": "Linkler (her satira bir tane):",
        "paste": "Yapistir",
        "outdir": "Kayit klasoru:",
        "browse": "Gozat...",
        "format": "Kalite:",
        "conc": "Ayni anda:",
        "notify": "Bitince bildir",
        "archive": "Indirileni tekrar indirme",
        "cookies": "Cerez:",
        "cookie_opts": ["Yok", "Tarayici", "cookies.txt dosyasi"],
        "cookiefile": "cookies.txt:",
        "pickfile": "Dosya sec...",
        "cf_ok": "✔ Instagram girisi var",
        "cf_nologin": "✗ Instagram girisi yok (instagram.com'da tekrar aktar)",
        "cf_none": "✗ dosya secilmedi",
        "lang": "Dil:",
        "dark": "Karanlik mod",
        "download": "Indir",
        "openfolder": "Klasoru Ac",
        "clear": "Temizle",
        "howto": "(i) Nasil kullanilir",
        "setup": "Kurulum / Guncelle",
        "help_title": "Nasil kullanilir",
        "help_text": HELP_TR,
        "status_label": "Durum:",
        "ready": "Hazir.",
        "ffmpeg_ok": "ffmpeg bulundu.",
        "ffmpeg_warn": "UYARI: ffmpeg bulunamadi, ses/video ayri kalabilir.",
        "warn": "Uyari",
        "info": "Bilgi",
        "no_links": "En az bir link girin.",
        "need_cookiefile": "Gecerli bir cookies.txt dosyasi secin.",
        "folder_not_yet": "Klasor henuz olusmadi.",
        "clip_empty": "Pano bos veya metin degil.",
        "started": "--- {n} link icin indirme basladi ---",
        "starting": "basliyor",
        "merging": "birlestiriliyor/bitti",
        "pp_already": "{v}/{a}, sabit fps -> donusturme gerekmedi",
        "pp_recoding": "{v}/{a} -> H.264/AAC'ye cevriliyor (sabit fps)...",
        "pp_done": "cevrildi -> H.264/AAC (sabit fps)",
        "pp_fail": "donusturme BASARISIZ, {v}/{a} olarak kaldi",
        "ok": "TAMAM",
        "error": "HATA",
        "finished_all": "--- Tum islemler bitti ---",
        "progress": "Ilerleme: {d}/{t} tamamlandi",
        "done": "Bitti: {d}/{t}",
        "notify_title": "Indirmeler bitti",
        "notify_msg": "{d}/{t} indirme tamamlandi.",
        "setup_running": "Kurulum: yt-dlp ve ffmpeg yukleniyor/guncelleniyor... bir dakika surebilir.",
        "setup_ok": "Kurulum tamam: yt-dlp guncellendi, ffmpeg hazir. Emin olmak icin yeniden ac.",
        "setup_ffmpeg_fail": "yt-dlp guncellendi ama ffmpeg kurulamadi. 'Nasil kullanilir'a bak.",
        "hint_chrome_enc": "Chrome/Edge cerezleri sifreliyor (v127+) ve yt-dlp cozemiyor. Bunun yerine cookies.txt dosyasi kullan (Cerez -> cookies.txt dosyasi) - tarayici acikken bile calisir. 'Get cookies.txt LOCALLY' eklentisiyle disa aktar.",
        "hint_browser_open": "{b} ACIK oldugu icin cerezleri kilitli. {b}'i tamamen kapat, ya da cookies.txt dosyasi kullan (onerilir - tarayici acikken bile calisir).",
        "hint_cookiefile": "cookies.txt dosyasi okunamadi. Tarayicidan disa aktarilmis gecerli bir dosya sec.",
        "hint_login": "Bu gonderi giris gerektiriyor. Cerez'i Tarayici (ve o tarayiciyi kapat) ya da cookies.txt dosyasi yap.",
        "preflight_title": "Tarayici acik",
        "preflight_msg": "{b} acik, cerezler okunamaz ve indirmeler basarisiz olur.\n\n{b}'i tamamen kapatip tekrar dene, ya da Cerez'i 'cookies.txt dosyasi' yap.\n\nYine de devam edilsin mi?",
        "ig_title": "Instagram girisi yok",
        "ig_no_login": "cookies.txt dosyanda Instagram girisi yok ('sessionid' cerezi eksik), bu yuzden Instagram linkleri calismaz.\n\nTarayicida: instagram.com'u ac, giris yaptigindan emin ol, sonra instagram.com sekmesi ACIKKEN cookies.txt'yi tekrar disa aktar.\n\nYine de devam edilsin mi?",
    },
}

# Quality dropdown values (not localized - technical keys)
FORMAT_VALUES = ["best", "1080", "720", "mp3"]

# Browser -> process image name (for "is it running?" preflight check)
BROWSER_EXE = {
    "chrome": "chrome.exe", "edge": "msedge.exe", "firefox": "firefox.exe",
    "brave": "brave.exe", "opera": "opera.exe", "vivaldi": "vivaldi.exe",
    "chromium": "chrome.exe",
}


# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------
DEFAULTS = {
    "lang": "en",
    "outdir": os.path.join(os.environ.get("USERPROFILE", "."), "Downloads", "ClipFetch"),
    "format": "best",
    "conc": 3,
    "cookie_mode": 0,   # 0 none, 1 browser, 2 file
    "browser": "chrome",
    "cookiefile": "",
    "notify": True,
    "archive": False,
    "dark": True,
}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# ffmpeg / ffprobe (winget install may not be on PATH yet)
# ---------------------------------------------------------------------------
def find_ffmpeg():
    from shutil import which
    p = which("ffmpeg")
    if p:
        return os.path.dirname(p)
    # a portable copy downloaded next to the app
    for pattern in (
        os.path.join(APP_DIR, "ffmpeg", "**", "ffmpeg.exe"),
        os.path.join(APP_DIR, "bin", "ffmpeg.exe"),
    ):
        hits = glob.glob(pattern, recursive=True)
        if hits:
            return os.path.dirname(hits[0])
    # winget install location
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""),
                        "Microsoft", "WinGet", "Packages")
    for pattern in (
        os.path.join(base, "Gyan.FFmpeg*", "ffmpeg-*", "bin", "ffmpeg.exe"),
        os.path.join(base, "*FFmpeg*", "**", "ffmpeg.exe"),
    ):
        hits = glob.glob(pattern, recursive=True)
        if hits:
            return os.path.dirname(hits[0])
    return None


def _tool(name):
    if FFMPEG_DIR:
        p = os.path.join(FFMPEG_DIR, name)
        if os.path.isfile(p):
            return p
    from shutil import which
    return which(name.replace(".exe", "")) or name


FFMPEG_DIR = find_ffmpeg()
FFMPEG = _tool("ffmpeg.exe")
FFPROBE = _tool("ffprobe.exe")


def refresh_ffmpeg():
    """Recompute ffmpeg/ffprobe locations after an install."""
    global FFMPEG_DIR, FFMPEG, FFPROBE
    FFMPEG_DIR = find_ffmpeg()
    FFMPEG = _tool("ffmpeg.exe")
    FFPROBE = _tool("ffprobe.exe")


FFMPEG_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def ensure_ytdlp(log=lambda s: None):
    """Update yt-dlp to the latest version."""
    try:
        return _pip_install("yt-dlp").returncode == 0
    except Exception as e:
        log(str(e))
        return False


def ensure_ffmpeg(log=lambda s: None):
    """Make sure ffmpeg+ffprobe are available. Try winget, then a portable download."""
    if FFMPEG_DIR:
        return True
    # 1) winget (Windows)
    try:
        _run_hidden(["winget", "install", "--id", "Gyan.FFmpeg", "-e",
                     "--accept-package-agreements", "--accept-source-agreements",
                     "--disable-interactivity"])
        refresh_ffmpeg()
    except Exception:
        pass
    if FFMPEG_DIR:
        return True
    # 2) portable download + extract next to the app
    log("ffmpeg indiriliyor / downloading ffmpeg (~80 MB)...")
    dest = os.path.join(APP_DIR, "ffmpeg")
    os.makedirs(dest, exist_ok=True)
    zippath = os.path.join(dest, "_ffmpeg.zip")
    try:
        urllib.request.urlretrieve(FFMPEG_ZIP_URL, zippath)
        with zipfile.ZipFile(zippath) as z:
            z.extractall(dest)
        os.remove(zippath)
    except Exception as e:
        log("ffmpeg indirme hatasi / download failed: %s" % e)
        return False
    refresh_ffmpeg()
    return bool(FFMPEG_DIR)


def _run_hidden(cmd):
    """Run a command with no console window; return CompletedProcess."""
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return subprocess.run(cmd, capture_output=True, text=True,
                          creationflags=0x08000000, startupinfo=si)


def is_process_running(exe):
    try:
        out = _run_hidden(["tasklist", "/FI", f"IMAGENAME eq {exe}", "/NH"]).stdout or ""
        return exe.lower() in out.lower()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Premiere compatibility: re-encode to H.264/AAC only if needed
# ---------------------------------------------------------------------------
def _rate(s):
    """Parse an ffprobe frame-rate fraction like '30000/1001' to float."""
    try:
        n, d = s.split("/")
        d = float(d)
        return float(n) / d if d else 0.0
    except Exception:
        return 0.0


def _probe_streams(path):
    """Return (video_codec, audio_codec, pix_fmt, is_cfr).
    is_cfr is False for variable-frame-rate or unknown-rate video (Premiere hates VFR)."""
    try:
        out = _run_hidden([
            FFPROBE, "-v", "error",
            "-show_entries", "stream=codec_type,codec_name,pix_fmt,r_frame_rate,avg_frame_rate",
            "-of", "json", path,
        ]).stdout
        data = json.loads(out)
        v = a = pix = ""
        is_cfr = False
        for st in data.get("streams", []):
            if st.get("codec_type") == "video" and not v:
                v = st.get("codec_name", "")
                pix = st.get("pix_fmt", "")
                r = _rate(st.get("r_frame_rate", "0/0"))
                avg = _rate(st.get("avg_frame_rate", "0/0"))
                # constant frame rate only if both known and (nearly) equal
                is_cfr = r > 0 and avg > 0 and abs(r - avg) < 0.05
            elif st.get("codec_type") == "audio" and not a:
                a = st.get("codec_name", "")
        return v, a, pix, is_cfr
    except Exception:
        return "", "", "", True  # can't probe -> don't force a re-encode


def _is_compat(v, a, pix, is_cfr):
    return (v == "h264"
            and (a in ("aac", ""))
            and (pix in ("yuv420p", "yuvj420p", ""))
            and is_cfr)


def is_premiere_compatible(path):
    v, a, pix, is_cfr = _probe_streams(path)
    return _is_compat(v, a, pix, is_cfr)


def make_premiere_compatible(path, report=lambda status, v, a: None):
    """Re-encode to H.264/AAC/yuv420p mp4 if not already Premiere-friendly.
    Calls report(status, vcodec, acodec) so the GUI can log every action.
    """
    if not path or not os.path.isfile(path):
        return
    v, a, pix, is_cfr = _probe_streams(path)
    if _is_compat(v, a, pix, is_cfr):
        report("already", v, a)
        return
    report("recoding", v, a)
    root, _ = os.path.splitext(path)
    tmp = root + ".premiere.mp4"
    r = _run_hidden([
        FFMPEG, "-y", "-v", "error", "-i", path,
        "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-fps_mode", "cfr",                    # variable -> constant frame rate (fixes Premiere importerMPEG)
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", tmp,
    ])
    if r.returncode == 0 and os.path.isfile(tmp):
        try:
            os.replace(tmp, path)
            report("done", "h264", "aac")
            return
        except Exception:
            pass
    try:
        if os.path.isfile(tmp):
            os.remove(tmp)
    except Exception:
        pass
    report("fail", v, a)


class PremierePP(PostProcessor):
    """yt-dlp post-processor that ensures the final file plays in Premiere."""
    def __init__(self, report=lambda status, v, a: None):
        super().__init__()
        self._report = report

    def run(self, info):
        make_premiere_compatible(info.get("filepath"), self._report)
        return [], info


def cookiefile_has_instagram_login(path):
    """True if the cookies.txt contains an Instagram sessionid (logged-in)."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "instagram" in line and "sessionid" in line:
                    parts = line.split("\t")
                    if len(parts) >= 7 and parts[5].strip() == "sessionid" and parts[6].strip():
                        return True
        return False
    except Exception:
        return True


def cookie_error_hint(app, msg, cmode, browser):
    m = (msg or "").lower()
    if cmode == 1 and ("dpapi" in m or "decrypt" in m):
        return app.L("hint_chrome_enc")
    if "cookie" in m and cmode == 1:
        return app.L("hint_browser_open").format(b=browser)
    if "cookie" in m and cmode == 2:
        return app.L("hint_cookiefile")
    if ("empty media response" in m or "login" in m or "rate-limit" in m
            or "requested content is not available" in m or "restricted" in m):
        return app.L("hint_login")
    return ""


# ---------------------------------------------------------------------------
# Format + cookie options -> yt-dlp opts
# ---------------------------------------------------------------------------
def build_opts(fmt_key, outdir, cookie_mode, browser, cookiefile, hook, archive):
    opts = {
        "outtmpl": os.path.join(outdir, "%(title).150B [%(id)s].%(ext)s"),
        "ignoreerrors": True,
        "noplaylist": False,
        "progress_hooks": [hook],
        "quiet": True,
        "no_warnings": True,
        "windowsfilenames": True,
    }
    if FFMPEG_DIR:
        opts["ffmpeg_location"] = FFMPEG_DIR
    if archive:
        opts["download_archive"] = os.path.join(outdir, "download_archive.txt")

    if fmt_key == "mp3":
        opts["format"] = "ba/b"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    elif fmt_key == "1080":
        opts["format"] = ("bv*[vcodec~='^(avc|h264)'][height<=1080]+ba[acodec~='^(mp4a|aac)']/"
                          "b[vcodec~='^(avc|h264)'][height<=1080]/bv*[height<=1080]+ba/b[height<=1080]/b")
        opts["merge_output_format"] = "mp4"
    elif fmt_key == "720":
        opts["format"] = ("bv*[vcodec~='^(avc|h264)'][height<=720]+ba[acodec~='^(mp4a|aac)']/"
                          "b[vcodec~='^(avc|h264)'][height<=720]/bv*[height<=720]+ba/b[height<=720]/b")
        opts["merge_output_format"] = "mp4"
    else:  # best - prefer H.264/AAC for editor (Premiere) compatibility
        opts["format"] = ("bv*[vcodec~='^(avc|h264)']+ba[acodec~='^(mp4a|aac)']/"
                          "b[vcodec~='^(avc|h264)']/bv*+ba/b")
        opts["merge_output_format"] = "mp4"

    if cookie_mode == 1 and browser:
        opts["cookiesfrombrowser"] = (browser,)
    elif cookie_mode == 2 and cookiefile and os.path.isfile(cookiefile):
        opts["cookiefile"] = cookiefile

    return opts


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        if self.cfg.get("format") not in FORMAT_VALUES:
            self.cfg["format"] = "best"
        self.lang = self.cfg.get("lang", "en")

        self.geometry("800x720")
        self.minsize(720, 640)

        self.msg_q = queue.Queue()
        self.executor = None
        self.running = False
        self.total = 0
        self.done = 0
        self.fracs = {}

        self.style = ttk.Style(self)
        self.dark = tk.BooleanVar(value=bool(self.cfg.get("dark", True)))

        self._build_ui()
        self._retext()
        self._apply_theme()
        self._check_cookiefile()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._drain_queue)

    def L(self, key):
        return STR[self.lang][key]

    def _apply_theme(self):
        dark = self.dark.get()
        if dark:
            bg, fg = "#1e1e1e", "#e6e6e6"
            ebg, sel = "#2b2b2b", "#0e639c"
            btn, muted = "#3a3a3a", "#9a9a9a"
            logbg, logfg = "#121212", "#e0e0e0"
        else:
            bg, fg = "#f0f0f0", "#101010"
            ebg, sel = "#ffffff", "#3399ff"
            btn, muted = "#e1e1e1", "#555555"
            logbg, logfg = "#111111", "#dddddd"

        s = self.style
        s.theme_use("clam")
        s.configure(".", background=bg, foreground=fg, fieldbackground=ebg,
                    bordercolor=btn, lightcolor=btn, darkcolor=btn)
        s.configure("TFrame", background=bg)
        s.configure("TLabel", background=bg, foreground=fg)
        s.configure("TCheckbutton", background=bg, foreground=fg)
        s.map("TCheckbutton", background=[("active", bg)])
        s.configure("TButton", background=btn, foreground=fg)
        s.map("TButton", background=[("active", sel), ("pressed", sel)])
        s.configure("TEntry", fieldbackground=ebg, foreground=fg, insertcolor=fg)
        s.configure("TCombobox", fieldbackground=ebg, foreground=fg,
                    background=btn, arrowcolor=fg)
        s.map("TCombobox", fieldbackground=[("readonly", ebg)],
              foreground=[("readonly", fg)])
        s.configure("TSpinbox", fieldbackground=ebg, foreground=fg,
                    background=btn, arrowcolor=fg)
        s.configure("Horizontal.TProgressbar", background=sel, troughcolor=ebg)

        # dropdown list popups
        self.option_add("*TCombobox*Listbox.background", ebg)
        self.option_add("*TCombobox*Listbox.foreground", fg)
        self.option_add("*TCombobox*Listbox.selectBackground", sel)
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

        self.configure(bg=bg)
        self.txt.configure(bg=ebg, fg=fg, insertbackground=fg,
                           selectbackground=sel, selectforeground="#ffffff")
        self.log.configure(bg=logbg, fg=logfg, insertbackground=logfg)
        self.lbl_statustext.configure(foreground=muted)
        # re-apply cookie status color (green/red) after theme change
        self._check_cookiefile()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # Top: language
        top = ttk.Frame(self); top.pack(fill="x", **pad)
        self.lbl_lang = ttk.Label(top, text="")
        self.lbl_lang.pack(side="right")
        self.lang_var = tk.StringVar(value="English" if self.lang == "en" else "Türkçe")
        cb = ttk.Combobox(top, textvariable=self.lang_var, width=10, state="readonly",
                          values=["English", "Türkçe"])
        cb.pack(side="right", padx=6)
        cb.bind("<<ComboboxSelected>>", self._on_lang)
        self.chk_dark = ttk.Checkbutton(top, text="", variable=self.dark,
                                        command=self._apply_theme)
        self.chk_dark.pack(side="left")

        # Links label + paste
        lrow = ttk.Frame(self); lrow.pack(fill="x", **pad)
        self.lbl_links = ttk.Label(lrow, text="")
        self.lbl_links.pack(side="left")
        self.btn_paste = ttk.Button(lrow, text="", width=10, command=self._paste)
        self.btn_paste.pack(side="right")
        self.txt = tk.Text(self, height=8, wrap="none")
        self.txt.pack(fill="both", expand=True, padx=8)

        # Save folder
        frm1 = ttk.Frame(self); frm1.pack(fill="x", **pad)
        self.lbl_outdir = ttk.Label(frm1, text="")
        self.lbl_outdir.pack(side="left")
        self.outdir = tk.StringVar(value=self.cfg.get("outdir", DEFAULTS["outdir"]))
        ttk.Entry(frm1, textvariable=self.outdir).pack(side="left", fill="x", expand=True, padx=6)
        self.btn_browse = ttk.Button(frm1, text="", command=self._pick_dir)
        self.btn_browse.pack(side="left")

        # Format + concurrency + options
        frm2 = ttk.Frame(self); frm2.pack(fill="x", **pad)
        self.lbl_format = ttk.Label(frm2, text="")
        self.lbl_format.pack(side="left")
        self.fmt = tk.StringVar(value=self.cfg.get("format", "best"))
        ttk.Combobox(frm2, textvariable=self.fmt, width=10, state="readonly",
                     values=FORMAT_VALUES).pack(side="left", padx=6)
        self.lbl_conc = ttk.Label(frm2, text="")
        self.lbl_conc.pack(side="left", padx=(12, 0))
        self.conc = tk.IntVar(value=int(self.cfg.get("conc", 3)))
        ttk.Spinbox(frm2, from_=1, to=8, width=4, textvariable=self.conc).pack(side="left", padx=6)
        self.notify = tk.BooleanVar(value=bool(self.cfg.get("notify", True)))
        self.chk_notify = ttk.Checkbutton(frm2, text="", variable=self.notify)
        self.chk_notify.pack(side="left", padx=(12, 0))
        self.archive = tk.BooleanVar(value=bool(self.cfg.get("archive", False)))
        self.chk_archive = ttk.Checkbutton(frm2, text="", variable=self.archive)
        self.chk_archive.pack(side="left", padx=(12, 0))

        # Cookies mode
        frm3 = ttk.Frame(self); frm3.pack(fill="x", **pad)
        self.lbl_cookies = ttk.Label(frm3, text="")
        self.lbl_cookies.pack(side="left")
        self.cookie_mode = tk.IntVar(value=int(self.cfg.get("cookie_mode", 0)))
        self.cb_cookie = ttk.Combobox(frm3, width=18, state="readonly")
        self.cb_cookie.pack(side="left", padx=6)
        self.cb_cookie.bind("<<ComboboxSelected>>", self._on_cookie_mode)
        self.browser = tk.StringVar(value=self.cfg.get("browser", "chrome"))
        self.cb_browser = ttk.Combobox(frm3, textvariable=self.browser, width=10, state="readonly",
                                       values=list(BROWSER_EXE.keys()))
        self.cb_browser.pack(side="left", padx=6)

        # cookies.txt file + live status
        frm3b = ttk.Frame(self); frm3b.pack(fill="x", **pad)
        self.lbl_cookiefile = ttk.Label(frm3b, text="")
        self.lbl_cookiefile.pack(side="left")
        self.cookiefile = tk.StringVar(value=self.cfg.get("cookiefile", ""))
        self.ent_cookiefile = ttk.Entry(frm3b, textvariable=self.cookiefile)
        self.ent_cookiefile.pack(side="left", fill="x", expand=True, padx=6)
        self.btn_pickfile = ttk.Button(frm3b, text="", command=self._pick_cookiefile)
        self.btn_pickfile.pack(side="left")
        self.lbl_cf_status = ttk.Label(self, text="")
        self.lbl_cf_status.pack(anchor="w", padx=12)
        self.cookiefile.trace_add("write", self._check_cookiefile)

        # Buttons
        frm4 = ttk.Frame(self); frm4.pack(fill="x", **pad)
        self.btn = ttk.Button(frm4, text="", command=self._start)
        self.btn.pack(side="left")
        self.btn_open = ttk.Button(frm4, text="", command=self._open_dir)
        self.btn_open.pack(side="left", padx=6)
        self.btn_clear = ttk.Button(frm4, text="", command=lambda: self.txt.delete("1.0", "end"))
        self.btn_clear.pack(side="left")
        self.btn_setup = ttk.Button(frm4, text="", command=self._setup_deps)
        self.btn_setup.pack(side="right")
        self.btn_howto = ttk.Button(frm4, text="", command=self._show_help)
        self.btn_howto.pack(side="right", padx=6)

        # Progress
        self.progress = ttk.Progressbar(self, mode="determinate", maximum=100)
        self.progress.pack(fill="x", padx=8, pady=(6, 2))
        self.status = tk.StringVar(value="")
        self.lbl_statustext = ttk.Label(self, textvariable=self.status)
        self.lbl_statustext.pack(anchor="w", **pad)

        # Log
        self.lbl_status = ttk.Label(self, text="")
        self.lbl_status.pack(anchor="w", padx=8)
        self.log = tk.Text(self, height=8, state="disabled", wrap="word", bg="#111", fg="#ddd")
        self.log.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._sync_cookie_state()

    # ---- language / retext ----
    def _on_lang(self, _e=None):
        self.lang = "en" if self.lang_var.get() == "English" else "tr"
        self._retext()
        self._check_cookiefile()

    def _retext(self):
        self.title(self.L("title"))
        self.lbl_lang.configure(text=self.L("lang"))
        self.chk_dark.configure(text=self.L("dark"))
        self.lbl_links.configure(text=self.L("links"))
        self.btn_paste.configure(text=self.L("paste"))
        self.lbl_outdir.configure(text=self.L("outdir"))
        self.btn_browse.configure(text=self.L("browse"))
        self.lbl_format.configure(text=self.L("format"))
        self.lbl_conc.configure(text=self.L("conc"))
        self.chk_notify.configure(text=self.L("notify"))
        self.chk_archive.configure(text=self.L("archive"))
        self.lbl_cookies.configure(text=self.L("cookies"))
        self.lbl_cookiefile.configure(text=self.L("cookiefile"))
        self.btn_pickfile.configure(text=self.L("pickfile"))
        self.btn.configure(text=self.L("download"))
        self.btn_open.configure(text=self.L("openfolder"))
        self.btn_clear.configure(text=self.L("clear"))
        self.btn_setup.configure(text=self.L("setup"))
        self.btn_howto.configure(text=self.L("howto"))
        self.lbl_status.configure(text=self.L("status_label"))

        idx = self.cookie_mode.get()
        self.cb_cookie.configure(values=self.L("cookie_opts"))
        self.cb_cookie.current(idx)

        ff = self.L("ffmpeg_ok") if FFMPEG_DIR else self.L("ffmpeg_warn")
        if not self.running:
            self.status.set(self.L("ready") + " " + ff)

    # ---- cookie mode ----
    def _on_cookie_mode(self, _e=None):
        self.cookie_mode.set(self.cb_cookie.current())
        self._sync_cookie_state()
        self._check_cookiefile()

    def _sync_cookie_state(self):
        m = self.cookie_mode.get()
        self.cb_browser.configure(state="readonly" if m == 1 else "disabled")
        st = "normal" if m == 2 else "disabled"
        self.ent_cookiefile.configure(state=st)
        self.btn_pickfile.configure(state=("normal" if m == 2 else "disabled"))

    def _check_cookiefile(self, *_):
        if self.cookie_mode.get() != 2:
            self.lbl_cf_status.configure(text="")
            return
        p = self.cookiefile.get()
        if not p or not os.path.isfile(p):
            self.lbl_cf_status.configure(text=self.L("cf_none"), foreground="#c33")
        elif cookiefile_has_instagram_login(p):
            self.lbl_cf_status.configure(text=self.L("cf_ok"), foreground="#2a2")
        else:
            self.lbl_cf_status.configure(text=self.L("cf_nologin"), foreground="#c33")

    # ---- helpers ----
    def _paste(self):
        try:
            data = self.clipboard_get()
        except Exception:
            data = ""
        if not data.strip():
            messagebox.showinfo(self.L("info"), self.L("clip_empty"))
            return
        cur = self.txt.get("1.0", "end").strip()
        if cur:
            self.txt.insert("end", "\n")
        self.txt.insert("end", data.strip())

    def _pick_dir(self):
        d = filedialog.askdirectory(initialdir=self.outdir.get() or ".")
        if d:
            self.outdir.set(d)

    def _pick_cookiefile(self):
        f = filedialog.askopenfilename(
            filetypes=[("cookies.txt", "*.txt"), ("All files", "*.*")])
        if f:
            self.cookiefile.set(f)

    def _open_dir(self):
        d = self.outdir.get()
        if os.path.isdir(d):
            os.startfile(d)
        else:
            messagebox.showinfo(self.L("info"), self.L("folder_not_yet"))

    def _logline(self, s):
        self.log.configure(state="normal")
        self.log.insert("end", s + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _collect_cfg(self):
        return {
            "lang": self.lang,
            "outdir": self.outdir.get(),
            "format": self.fmt.get(),
            "conc": int(self.conc.get()),
            "cookie_mode": self.cookie_mode.get(),
            "browser": self.browser.get(),
            "cookiefile": self.cookiefile.get(),
            "notify": bool(self.notify.get()),
            "archive": bool(self.archive.get()),
            "dark": bool(self.dark.get()),
        }

    def _on_close(self):
        save_config(self._collect_cfg())
        self.destroy()

    def _setup_deps(self):
        self.btn_setup.configure(state="disabled")
        self._logline(self.L("setup_running"))

        def work():
            ensure_ytdlp(lambda s: self.msg_q.put(("log", s)))
            ok = ensure_ffmpeg(lambda s: self.msg_q.put(("log", s)))
            self.msg_q.put(("log", self.L("setup_ok") if ok else self.L("setup_ffmpeg_fail")))
            ff = self.L("ffmpeg_ok") if FFMPEG_DIR else self.L("ffmpeg_warn")
            self.msg_q.put(("status", self.L("ready") + " " + ff))
            self.msg_q.put(("enable_setup", None))

        threading.Thread(target=work, daemon=True).start()

    def _show_help(self):
        win = tk.Toplevel(self)
        win.title(self.L("help_title"))
        win.geometry("660x580")
        dark = self.dark.get()
        bg = "#1e1e1e" if dark else "#ffffff"
        fg = "#e6e6e6" if dark else "#101010"
        win.configure(bg=bg)
        sb = ttk.Scrollbar(win)
        sb.pack(side="right", fill="y")
        txt = tk.Text(win, wrap="word", bg=bg, fg=fg, insertbackground=fg,
                      padx=14, pady=12, relief="flat", yscrollcommand=sb.set)
        txt.pack(fill="both", expand=True)
        sb.configure(command=txt.yview)
        txt.insert("1.0", self.L("help_text"))
        txt.configure(state="disabled")

    def _drain_queue(self):
        try:
            while True:
                kind, payload = self.msg_q.get_nowait()
                if kind == "log":
                    self._logline(payload)
                elif kind == "status":
                    self.status.set(payload)
                elif kind == "frac":
                    idx, f = payload
                    self.fracs[idx] = f
                    self._update_progress()
                elif kind == "enable_setup":
                    self.btn_setup.configure(state="normal")
                elif kind == "done_one":
                    self.done += 1
                    self.fracs[payload] = 1.0
                    self._update_progress()
                    self.status.set(self.L("progress").format(d=self.done, t=self.total))
                    if self.done >= self.total:
                        self._finish()
        except queue.Empty:
            pass
        self.after(120, self._drain_queue)

    def _update_progress(self):
        if self.total:
            pct = min(100.0, sum(self.fracs.values()) / self.total * 100.0)
            self.progress["value"] = pct

    # ---- download ----
    def _start(self):
        if self.running:
            return
        links = [l.strip() for l in self.txt.get("1.0", "end").splitlines() if l.strip()]
        if not links:
            messagebox.showwarning(self.L("warn"), self.L("no_links"))
            return
        if self.cookie_mode.get() == 2 and not os.path.isfile(self.cookiefile.get()):
            messagebox.showwarning(self.L("warn"), self.L("need_cookiefile"))
            return
        if (self.cookie_mode.get() == 2
                and any("instagram.com" in u for u in links)
                and not cookiefile_has_instagram_login(self.cookiefile.get())):
            if not messagebox.askyesno(self.L("ig_title"), self.L("ig_no_login")):
                return
        if self.cookie_mode.get() == 1:
            exe = BROWSER_EXE.get(self.browser.get(), "")
            if exe and is_process_running(exe):
                if not messagebox.askyesno(self.L("preflight_title"),
                                           self.L("preflight_msg").format(b=self.browser.get())):
                    return

        outdir = self.outdir.get().strip()
        os.makedirs(outdir, exist_ok=True)
        save_config(self._collect_cfg())

        self.running = True
        self.done = 0
        self.total = len(links)
        self.fracs = {}
        self.progress["value"] = 0
        self.btn.configure(state="disabled")
        self._logline(self.L("started").format(n=self.total))

        fmt = self.fmt.get()
        cmode = self.cookie_mode.get()
        browser = self.browser.get()
        cfile = self.cookiefile.get()
        archive = bool(self.archive.get())
        conc = max(1, int(self.conc.get()))

        def worker(idx, url):
            tag = f"[{idx}]"

            def hook(d):
                if d["status"] == "downloading":
                    tot = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    dl = d.get("downloaded_bytes") or 0
                    self.msg_q.put(("frac", (idx, (dl / tot) if tot else 0)))
                    pct = d.get("_percent_str", "").strip()
                    spd = d.get("_speed_str", "").strip()
                    self.msg_q.put(("status", f"{tag} {pct} {spd}"))
                elif d["status"] == "finished":
                    self.msg_q.put(("frac", (idx, 1.0)))
                    self.msg_q.put(("log", f"{tag} {self.L('merging')}: "
                                           f"{os.path.basename(d.get('filename',''))}"))

            def report(status, vcodec, acodec):
                txt = self.L("pp_" + status).format(v=vcodec or "?", a=acodec or "?")
                self.msg_q.put(("log", f"{tag}    -> {txt}"))

            opts = build_opts(fmt, outdir, cmode, browser, cfile, hook, archive)
            self.msg_q.put(("log", f"{tag} {self.L('starting')}: {url}"))
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    if fmt != "mp3":
                        ydl.add_post_processor(PremierePP(report), when="after_move")
                    code = ydl.download([url])
                key = "ok" if code == 0 else "error"
                self.msg_q.put(("log", f"{tag} {self.L(key)}: {url}"))
            except Exception as e:
                self.msg_q.put(("log", f"{tag} {self.L('error')}: {url} -> {e}"))
                hint = cookie_error_hint(self, str(e), cmode, browser)
                if hint:
                    self.msg_q.put(("log", f"    >> {hint}"))
            finally:
                self.msg_q.put(("done_one", idx))

        self.executor = ThreadPoolExecutor(max_workers=conc)
        for i, url in enumerate(links, 1):
            self.executor.submit(worker, i, url)

    def _finish(self):
        self.running = False
        self.btn.configure(state="normal")
        self.progress["value"] = 100
        self._logline(self.L("finished_all"))
        self.status.set(self.L("done").format(d=self.done, t=self.total))
        if self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None
        if self.notify.get():
            messagebox.showinfo(self.L("notify_title"),
                                self.L("notify_msg").format(d=self.done, t=self.total))


# ---------------------------------------------------------------------------
# CLI (terminal) mode
# ---------------------------------------------------------------------------
def run_cli(argv=None):
    p = argparse.ArgumentParser(
        prog="clipfetch.py",
        description="Video downloader (yt-dlp). Run with no arguments to open the GUI.")
    p.add_argument("urls", nargs="*", help="video links")
    p.add_argument("-f", "--format", default="best", choices=FORMAT_VALUES,
                   help="quality (default: best)")
    p.add_argument("-o", "--output", default=DEFAULTS["outdir"], help="output folder")
    p.add_argument("--audio", action="store_true", help="audio only (mp3)")
    p.add_argument("--cookies", help="path to a cookies.txt file")
    p.add_argument("--browser", help="read cookies from a browser (chrome, firefox, edge, ...)")
    p.add_argument("--archive", action="store_true", help="skip already-downloaded videos")
    p.add_argument("--no-fix", action="store_true",
                   help="do not auto-convert video to H.264/constant-fps")
    p.add_argument("--setup", action="store_true",
                   help="install/update yt-dlp and ffmpeg, then exit")
    args = p.parse_args(argv)

    if args.setup:
        print("yt-dlp guncelleniyor / updating yt-dlp...")
        ensure_ytdlp(print)
        print("ffmpeg kontrol ediliyor / checking ffmpeg...")
        ok = ensure_ffmpeg(print)
        print("Kurulum tamam." if ok else "ffmpeg kurulamadi / ffmpeg not installed.")
        if not args.urls:
            return

    if not args.urls:
        p.print_help()
        return

    fmt = "mp3" if args.audio else args.format
    cmode = 2 if args.cookies else (1 if args.browser else 0)
    outdir = args.output
    os.makedirs(outdir, exist_ok=True)
    if not FFMPEG_DIR:
        print("ffmpeg yok, kuruluyor / ffmpeg missing, installing...")
        ensure_ffmpeg(print)

    def report(status, v, a):
        print("   [%s] %s/%s" % (status, v or "?", a or "?"))

    def hook(d):
        if d["status"] == "downloading":
            print("\r  %s %s   " % (d.get("_percent_str", "").strip(),
                                     d.get("_speed_str", "").strip()), end="")
        elif d["status"] == "finished":
            print()

    ok_count = 0
    for i, url in enumerate(args.urls, 1):
        print("[%d/%d] %s" % (i, len(args.urls), url))
        opts = build_opts(fmt, outdir, cmode, args.browser or "chrome",
                          args.cookies or "", hook, args.archive)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                if fmt != "mp3" and not args.no_fix:
                    ydl.add_post_processor(PremierePP(report), when="after_move")
                code = ydl.download([url])
            if code == 0:
                ok_count += 1
                print("  OK")
            else:
                print("  HATA / ERROR (code %s)" % code)
        except Exception as e:
            print("  HATA / ERROR:", e)
    print("Bitti / Done: %d/%d" % (ok_count, len(args.urls)))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_cli()
    else:
        App().mainloop()
