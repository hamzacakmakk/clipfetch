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
import re
import time
import threading
import zipfile
import argparse
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont

FROZEN = getattr(sys, "frozen", False)   # running as the packaged ClipFetch.exe
# Settings and the downloaded ffmpeg live next to the script, or next to the .exe
APP_DIR = os.path.dirname(sys.executable if FROZEN else os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "clipfetch_config.json")


# curl-cffi lets yt-dlp impersonate a browser; TikTok and others block plain requests.
YTDLP_PKG = "yt-dlp[default,curl-cffi]"


def _pip_install(*pkgs):
    flags = 0x08000000 if os.name == "nt" else 0
    return subprocess.run([sys.executable, "-m", "pip", "install", "-U", *pkgs],
                          creationflags=flags)


# yt-dlp is required -> auto-install on first run if missing (fresh GitHub clone)
try:
    import yt_dlp
except ImportError:
    _pip_install(YTDLP_PKG)
    import yt_dlp
from yt_dlp.postprocessor import PostProcessor


# ---------------------------------------------------------------------------
# Help texts
# ---------------------------------------------------------------------------
HELP_EN = """Adding links
Paste links into the box, one per line, or press Paste. Any text works: ClipFetch picks the links out of it and drops duplicates. YouTube, Instagram, TikTok, X and every other site yt-dlp supports.

Quality
Best downloads the highest resolution available, up to 4K. 1080p and 720p cap the resolution. MP3 saves audio only.

Editor-ready files
With "Make editor-ready" on, the video format of every finished file is checked. If it uses AV1, VP9, Opus or a variable frame rate, it is converted to H.264/AAC at a constant frame rate, a video format Premiere and DaVinci import cleanly. The GPU is used for this when available. Files that are already in that format are left untouched.

Sign-in (Instagram and private posts)
Instagram does not serve posts to logged-out visitors, so you need cookies. Chrome and Edge encrypt their cookies, so the Browser option often fails. The reliable route is a cookies.txt file:
  1. Install the "Get cookies.txt LOCALLY" browser extension.
  2. Log in at instagram.com.
  3. With the instagram.com tab open, export cookies.txt from the extension.
  4. In ClipFetch choose Sign-in > cookies.txt and select the file.
A green "Instagram login found" means you are ready. cookies.txt holds your login session, so never share it.

The queue
Each link becomes a row with its own status, progress and details. Double-click a finished row to open the file; right-click for more options. Cancel stops the batch, and Retry failed runs only the links that did not finish.

Keyboard
  Ctrl+Enter   start / cancel
  Ctrl+L       focus the link box
  F1           this help

Update tools
Run it on first launch or when a site stops working. It updates yt-dlp and installs ffmpeg.

Command line
  python clipfetch.py <link1> <link2> ...
  python clipfetch.py -f 1080 -o "C:/downloads" <link>
  python clipfetch.py --audio <link>
  python clipfetch.py --cookies cookies.txt <link>
  python clipfetch.py --setup
Run without arguments to open the app.
"""

HELP_TR = """Link ekleme
Linkleri kutuya alt alta yapıştırın ya da Yapıştır'a basın. Her türlü metin olur: ClipFetch içindeki linkleri ayıklar, tekrar edenleri atar. YouTube, Instagram, TikTok, X ve yt-dlp'nin desteklediği tüm siteler.

Kalite
En iyi, bulunabilen en yüksek çözünürlüğü (4K'ya kadar) indirir. 1080p ve 720p çözünürlüğü sınırlar. MP3 sadece sesi kaydeder.

Kurgu programına hazır dosyalar
"Kurguya hazır yap" açıkken biten her video kontrol edilir. AV1, VP9, Opus ya da değişken kare hızı varsa Premiere ve DaVinci'nin sorunsuz açması için sabit kare hızlı H.264/AAC'ye çevrilir. Zaten uyumlu olan dosyalara dokunulmaz.

Giriş (Instagram ve gizli gönderiler)
Instagram giriş yapmamış ziyaretçiye gönderi göstermez, bu yüzden çerez gerekir. Chrome ve Edge çerezleri şifrelediği için Tarayıcı seçeneği çoğu zaman çalışmaz. En sağlam yol cookies.txt dosyasıdır:
  1. Tarayıcıya "Get cookies.txt LOCALLY" eklentisini kurun.
  2. instagram.com'a giriş yapın.
  3. instagram.com sekmesi açıkken eklentiden cookies.txt dışa aktarın.
  4. ClipFetch'te Giriş > cookies.txt seçip dosyayı gösterin.
Yeşil "Instagram girişi bulundu" yazısı hazır olduğunuzu gösterir. cookies.txt oturum bilginizi içerir, kimseyle paylaşmayın.

Kuyruk
Her link kendi durumu, ilerlemesi ve ayrıntısıyla bir satır olur. Biten satıra çift tıklayınca dosya açılır; sağ tık daha fazla seçenek sunar. İptal tüm işlemi durdurur, Başarısızları tekrar dene sadece bitmeyen linkleri yeniden çalıştırır.

Klavye
  Ctrl+Enter   başlat / iptal
  Ctrl+L       link kutusuna git
  F1           bu yardım

Araçları güncelle
İlk açılışta ya da bir site çalışmayı bıraktığında kullanın. yt-dlp'yi günceller, ffmpeg'i kurar.

Komut satırı
  python clipfetch.py <link1> <link2> ...
  python clipfetch.py -f 1080 -o "C:/indirilenler" <link>
  python clipfetch.py --audio <link>
  python clipfetch.py --cookies cookies.txt <link>
  python clipfetch.py --setup
Argümansız çalıştırınca uygulama açılır.
"""


# ---------------------------------------------------------------------------
# Language strings
# ---------------------------------------------------------------------------
STR = {
    "en": {
        "tagline": "Batch video downloader",
        "links": "Links",
        "count": "{n} links",
        "count_one": "1 link",
        "count_zero": "",
        "paste": "Paste",
        "clear": "Clear",
        "placeholder": "Paste links here, one per line.\nYouTube, Instagram, TikTok, X and many more sites work.",
        "tab_queue": "Queue",
        "tab_log": "Log",
        "empty_queue": "Downloads appear here.\nPaste links above and press Download.",
        "col_name": "Item",
        "col_status": "Status",
        "col_progress": "Progress",
        "col_detail": "Details",
        "save_to": "Save to",
        "quality": "Quality",
        "q_labels": ["Best", "1080p", "720p", "MP3"],
        "conc": "Parallel downloads",
        "fix": "Make editor-ready (H.264)",
        "archive": "Skip already downloaded",
        "notify": "Alert when finished",
        "signin": "Sign-in",
        "signin_hint": "Needed for Instagram and private posts.",
        "cookie_opts": ["None", "Browser", "cookies.txt"],
        "choose": "Choose",
        "cf_ok": "Instagram login found",
        "cf_nologin": "No Instagram login in this file",
        "cf_none": "No file selected",
        "download": "Download",
        "cancel": "Cancel",
        "cancelling": "Cancelling",
        "openfolder": "Open folder",
        "retry_failed": "Retry failed",
        "setup": "Update tools",
        "help": "Help",
        "theme_to_light": "Light mode",
        "theme_to_dark": "Dark mode",
        "lang_switch": "Türkçe",
        "help_title": "ClipFetch help",
        "help_text": HELP_EN,
        "ready": "Ready",
        "ffmpeg_ok": "ffmpeg found",
        "ffmpeg_warn": "ffmpeg missing, run Update tools",
        "warn": "Warning",
        "info": "Info",
        "no_links": "No links found. Paste at least one link that starts with http.",
        "need_cookiefile": "Select a valid cookies.txt file.",
        "folder_not_yet": "The folder does not exist yet.",
        "clip_empty": "The clipboard has no links.",
        "st_queued": "Queued",
        "st_downloading": "Downloading",
        "st_processing": "Processing",
        "st_converting": "Converting",
        "st_done": "Done",
        "st_failed": "Failed",
        "st_cancelled": "Cancelled",
        "skipped": "Already downloaded, skipped",
        "no_audio": "no audio",
        "pp_already": "Editor-ready ({v}/{a}), kept as is",
        "pp_recoding": "{v}/{a}, converting to H.264/AAC",
        "pp_done": "Converted to H.264/AAC, constant fps",
        "pp_fail": "Conversion failed, kept as {v}/{a}",
        "running": "{d} of {t} complete",
        "finished": "{ok} downloaded, {fail} failed",
        "finished_ok": "{ok} downloaded",
        "started": "Started {n} download(s)",
        "menu_open": "Open file",
        "menu_show": "Show in folder",
        "menu_copy": "Copy link",
        "menu_retry": "Retry",
        "menu_remove": "Remove from list",
        "setup_running": "Updating yt-dlp and ffmpeg. This can take a minute.",
        "setup_ok": "Tools updated. Restart ClipFetch to be safe.",
        "setup_ffmpeg_fail": "yt-dlp updated, but ffmpeg could not be installed. See Help.",
        "hint_chrome_enc": "Chrome/Edge encrypt their cookies and yt-dlp cannot read them. Use Sign-in > cookies.txt instead.",
        "hint_browser_open": "{b} is open, so its cookies are locked. Close it completely or use Sign-in > cookies.txt.",
        "hint_cookiefile": "The cookies.txt file could not be read. Export it again from your browser.",
        "hint_login": "This post needs a login. Set Sign-in to cookies.txt (see Help).",
        "preflight_title": "Browser is open",
        "preflight_msg": "{b} is open, so its cookies cannot be read and downloads will fail.\n\nClose {b} completely, or switch Sign-in to cookies.txt.\n\nContinue anyway?",
        "ig_title": "No Instagram login",
        "ig_no_login": "Your cookies.txt has no Instagram login (the sessionid cookie is missing), so Instagram links will fail.\n\nOpen instagram.com, make sure you are logged in, then export cookies.txt again with that tab open.\n\nContinue anyway?",
    },
    "tr": {
        "tagline": "Toplu video indirici",
        "links": "Linkler",
        "count": "{n} link",
        "count_one": "1 link",
        "count_zero": "",
        "paste": "Yapıştır",
        "clear": "Temizle",
        "placeholder": "Linkleri buraya alt alta yapıştırın.\nYouTube, Instagram, TikTok, X ve daha birçok site desteklenir.",
        "tab_queue": "Kuyruk",
        "tab_log": "Kayıt",
        "empty_queue": "İndirmeler burada görünür.\nYukarıya link yapıştırıp İndir'e basın.",
        "col_name": "Öğe",
        "col_status": "Durum",
        "col_progress": "İlerleme",
        "col_detail": "Ayrıntı",
        "save_to": "Kayıt yeri",
        "quality": "Kalite",
        "q_labels": ["En iyi", "1080p", "720p", "MP3"],
        "conc": "Aynı anda indirme",
        "fix": "Kurguya hazır yap (H.264)",
        "archive": "İndirilenleri atla",
        "notify": "Bitince haber ver",
        "signin": "Giriş",
        "signin_hint": "Instagram ve gizli gönderiler için gerekir.",
        "cookie_opts": ["Yok", "Tarayıcı", "cookies.txt"],
        "choose": "Seç",
        "cf_ok": "Instagram girişi bulundu",
        "cf_nologin": "Bu dosyada Instagram girişi yok",
        "cf_none": "Dosya seçilmedi",
        "download": "İndir",
        "cancel": "İptal",
        "cancelling": "İptal ediliyor",
        "openfolder": "Klasörü aç",
        "retry_failed": "Başarısızları tekrar dene",
        "setup": "Araçları güncelle",
        "help": "Yardım",
        "theme_to_light": "Açık tema",
        "theme_to_dark": "Koyu tema",
        "lang_switch": "English",
        "help_title": "ClipFetch yardım",
        "help_text": HELP_TR,
        "ready": "Hazır",
        "ffmpeg_ok": "ffmpeg bulundu",
        "ffmpeg_warn": "ffmpeg yok, Araçları güncelle'ye basın",
        "warn": "Uyarı",
        "info": "Bilgi",
        "no_links": "Link bulunamadı. http ile başlayan en az bir link yapıştırın.",
        "need_cookiefile": "Geçerli bir cookies.txt dosyası seçin.",
        "folder_not_yet": "Klasör henüz oluşmadı.",
        "clip_empty": "Panoda link yok.",
        "st_queued": "Sırada",
        "st_downloading": "İndiriliyor",
        "st_processing": "İşleniyor",
        "st_converting": "Dönüştürülüyor",
        "st_done": "Bitti",
        "st_failed": "Başarısız",
        "st_cancelled": "İptal edildi",
        "skipped": "Daha önce indirilmiş, atlandı",
        "no_audio": "ses yok",
        "pp_already": "Kurguya hazır ({v}/{a}), olduğu gibi kaldı",
        "pp_recoding": "{v}/{a}, H.264/AAC'ye çevriliyor",
        "pp_done": "H.264/AAC'ye çevrildi, sabit fps",
        "pp_fail": "Dönüştürme başarısız, {v}/{a} olarak kaldı",
        "running": "{t} işten {d} tamamlandı",
        "finished": "{ok} indirildi, {fail} başarısız",
        "finished_ok": "{ok} indirildi",
        "started": "{n} indirme başladı",
        "menu_open": "Dosyayı aç",
        "menu_show": "Klasörde göster",
        "menu_copy": "Linki kopyala",
        "menu_retry": "Tekrar dene",
        "menu_remove": "Listeden kaldır",
        "setup_running": "yt-dlp ve ffmpeg güncelleniyor. Bir dakika sürebilir.",
        "setup_ok": "Araçlar güncellendi. Emin olmak için ClipFetch'i yeniden açın.",
        "setup_ffmpeg_fail": "yt-dlp güncellendi ama ffmpeg kurulamadı. Yardım'a bakın.",
        "hint_chrome_enc": "Chrome/Edge çerezleri şifreliyor ve yt-dlp okuyamıyor. Giriş > cookies.txt kullanın.",
        "hint_browser_open": "{b} açık olduğu için çerezleri kilitli. Tamamen kapatın ya da Giriş > cookies.txt kullanın.",
        "hint_cookiefile": "cookies.txt okunamadı. Tarayıcıdan yeniden dışa aktarın.",
        "hint_login": "Bu gönderi giriş istiyor. Giriş'i cookies.txt yapın (Yardım'a bakın).",
        "preflight_title": "Tarayıcı açık",
        "preflight_msg": "{b} açık, çerezleri okunamaz ve indirmeler başarısız olur.\n\n{b}'i tamamen kapatın ya da Giriş'i cookies.txt yapın.\n\nYine de devam edilsin mi?",
        "ig_title": "Instagram girişi yok",
        "ig_no_login": "cookies.txt dosyanızda Instagram girişi yok (sessionid çerezi eksik), bu yüzden Instagram linkleri çalışmaz.\n\ninstagram.com'u açıp giriş yaptığınızdan emin olun, sonra o sekme açıkken cookies.txt'yi yeniden dışa aktarın.\n\nYine de devam edilsin mi?",
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
    "fix": True,
    "geometry": "",
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
    if FROZEN:
        # the .exe carries its own yt-dlp; pip is not available inside it
        log("yt-dlp " + yt_dlp.version.__version__ + " is built into this ClipFetch.exe. "
            "Download the latest release to update it.")
        return True
    try:
        return _pip_install(YTDLP_PKG).returncode == 0
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
    log("Downloading ffmpeg (about 80 MB)...")
    dest = os.path.join(APP_DIR, "ffmpeg")
    os.makedirs(dest, exist_ok=True)
    zippath = os.path.join(dest, "_ffmpeg.zip")
    try:
        urllib.request.urlretrieve(FFMPEG_ZIP_URL, zippath)
        with zipfile.ZipFile(zippath) as z:
            z.extractall(dest)
        os.remove(zippath)
    except Exception as e:
        log("ffmpeg download failed: %s" % e)
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


# H.264 encoders, fastest first. Hardware encoders are probed once and used when the
# GPU and driver support them; libx264 on the CPU is the fallback that always works.
HW_ENCODERS = [
    ("h264_nvenc", ["-preset", "p5", "-rc", "vbr", "-cq", "20", "-b:v", "0",
                    "-profile:v", "high", "-pix_fmt", "yuv420p"]),
    ("h264_qsv", ["-preset", "medium", "-global_quality", "20",
                  "-profile:v", "high", "-pix_fmt", "nv12"]),
    ("h264_amf", ["-quality", "quality", "-rc", "cqp", "-qp_i", "20", "-qp_p", "20",
                  "-profile:v", "high", "-pix_fmt", "yuv420p"]),
]
CPU_ENCODER = ("libx264", ["-preset", "veryfast", "-crf", "20",
                           "-profile:v", "high", "-pix_fmt", "yuv420p"])
_hw_lock = threading.Lock()
_hw_choice = None   # None = not probed yet, () = no working GPU encoder


def hw_encoder():
    """The first hardware H.264 encoder that actually works here, or None."""
    global _hw_choice
    with _hw_lock:
        if _hw_choice is None:
            _hw_choice = ()
            for name, args in HW_ENCODERS:
                try:
                    r = _run_hidden([FFMPEG, "-v", "error", "-f", "lavfi",
                                     "-i", "color=c=black:s=1920x1080:r=30", "-frames:v", "10",
                                     "-c:v", name, *args, "-f", "null", "-"])
                except Exception:
                    continue
                if r.returncode == 0:
                    _hw_choice = (name, args)
                    break
        return _hw_choice or None


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
    encoders = [e for e in (hw_encoder(), CPU_ENCODER) if e]
    r = None
    for name, args in encoders:
        r = _run_hidden([
            FFMPEG, "-y", "-v", "error", "-i", path,
            "-map", "0:v:0", "-map", "0:a?",
            "-c:v", name, *args,
            "-fps_mode", "cfr",                # variable -> constant frame rate (fixes Premiere importerMPEG)
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", tmp,
        ])
        if r.returncode == 0 and os.path.isfile(tmp):
            break
    if r is not None and r.returncode == 0 and os.path.isfile(tmp):
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
        "noprogress": True,
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
    else:
        # Take the highest resolution the site offers (4K included), whatever the codec.
        # At equal resolution prefer H.264/AAC so files that need no conversion skip it;
        # anything else (AV1, VP9, VFR) is converted to H.264 by PremierePP afterwards.
        cap = {"1080": 1080, "720": 720}.get(fmt_key)
        if cap:
            opts["format"] = f"bv*[height<={cap}]+ba/b[height<={cap}]/b"
            res = f"res:{cap}"
        else:
            opts["format"] = "bv*+ba/b"
            res = "res"
        opts["format_sort"] = [res, "fps", "hdr:sdr", "vcodec:h264", "acodec:aac"]
        opts["merge_output_format"] = "mp4"

    if cookie_mode == 1 and browser:
        opts["cookiesfrombrowser"] = (browser,)
    elif cookie_mode == 2 and cookiefile and os.path.isfile(cookiefile):
        opts["cookiefile"] = cookiefile

    return opts


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
URL_RE = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)


def extract_urls(text):
    """All http(s) links in a block of text, in order, without duplicates."""
    seen, out = set(), []
    for m in URL_RE.findall(text or ""):
        u = m.rstrip(").,;]}>")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def short_url(u, limit=64):
    s = u.split("://", 1)[-1]
    if s.startswith("www."):
        s = s[4:]
    return s if len(s) <= limit else s[:limit - 1] + "…"


PALETTE = {
    "dark": {
        "bg": "#111315", "surface": "#181a1d", "raised": "#212428", "border": "#2b2f34",
        "hover": "#2c3036", "text": "#e8e9eb", "muted": "#8d939b", "subtle": "#5f656d",
        "accent": "#3b7cf6", "accent_hover": "#5a91f8", "on_accent": "#ffffff",
        "select": "#1f2c44", "seg_fg": "#a9c6ff",
        "success": "#46b884", "danger": "#ef6262", "warning": "#e2a641",
    },
    "light": {
        "bg": "#f3f4f6", "surface": "#ffffff", "raised": "#f1f2f5", "border": "#dcdfe4",
        "hover": "#e6e8ec", "text": "#16181b", "muted": "#5f6670", "subtle": "#9ba1a9",
        "accent": "#2563eb", "accent_hover": "#1d4fd7", "on_accent": "#ffffff",
        "select": "#e3ecfd", "seg_fg": "#1d4fd7",
        "success": "#1d8a5a", "danger": "#cf3a3a", "warning": "#a86f12",
    },
}

# status key -> treeview tag
STATUS_TAG = {
    "queued": "muted", "downloading": "active", "processing": "active",
    "converting": "active", "done": "done", "failed": "failed", "cancelled": "muted",
}


class _ErrorLogger:
    """Collects yt-dlp error messages (they are swallowed with ignoreerrors)."""
    def __init__(self, sink):
        self.last = ""
        self._sink = sink

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        msg = str(msg).replace("ERROR: ", "", 1).strip()
        self.last = msg
        self._sink(msg)


class _InfoPP(PostProcessor):
    """Hands the info dict of each item to a callback (title, final path)."""
    def __init__(self, cb):
        super().__init__()
        self._cb = cb

    def run(self, info):
        self._cb(info)
        return [], info


def _app_icon(size=64, accent="#2563eb"):
    """Small download-arrow icon drawn in pixels (no image files needed)."""
    bg = None
    rows = []
    r = size * 0.22
    for y in range(size):
        row = []
        for x in range(size):
            # rounded square mask
            dx = max(r - x, 0, x - (size - 1 - r))
            dy = max(r - y, 0, y - (size - 1 - r))
            inside = dx * dx + dy * dy <= r * r
            if not inside:
                row.append(bg or "#000000")
                continue
            c = accent
            cx = size / 2
            u = x - cx
            # arrow shaft
            if abs(u) <= size * 0.07 and size * 0.20 <= y <= size * 0.52:
                c = "#ffffff"
            # arrow head
            top, bot = size * 0.40, size * 0.66
            if top <= y <= bot and abs(u) <= (bot - y) * 0.95:
                c = "#ffffff"
            # base line
            if size * 0.74 <= y <= size * 0.81 and abs(u) <= size * 0.27:
                c = "#ffffff"
            row.append(c)
        rows.append(row)
    img = tk.PhotoImage(width=size, height=size)
    img.put(" ".join("{" + " ".join(r) + "}" for r in rows))
    # make the corners transparent
    for y in range(size):
        for x in range(size):
            dx = max(r - x, 0, x - (size - 1 - r))
            dy = max(r - y, 0, y - (size - 1 - r))
            if dx * dx + dy * dy > r * r:
                img.transparency_set(x, y, True)
    return img


def _draw_check(img, size, scale, bg, border, fill, mark):
    """Paint a rounded checkbox into an existing PhotoImage (bg = outside colour)."""
    r = 3.5 * scale
    pts = [(0.27, 0.53), (0.44, 0.70), (0.75, 0.33)]
    pts = [(x * size, y * size) for x, y in pts]
    th = 1.15 * scale

    def seg_dist(px, py, a, b):
        (ax, ay), (bx, by) = a, b
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        cx, cy = ax + t * dx, ay + t * dy
        return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5

    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            px, py = x + 0.5, y + 0.5
            ex = max(r - px, 0, px - (size - r))
            ey = max(r - py, 0, py - (size - r))
            d = (ex * ex + ey * ey) ** 0.5
            if d > r:
                row.append(bg)
            elif d > r - 1.2 * scale or min(px, py, size - px, size - py) < 1.2 * scale:
                row.append(border if fill is None else fill)
            else:
                c = fill if fill is not None else bg_inner(border, bg)
                if mark and min(seg_dist(px, py, pts[0], pts[1]), seg_dist(px, py, pts[1], pts[2])) < th:
                    c = mark
                row.append(c)
        rows.append("{" + " ".join(row) + "}")
    img.put(" ".join(rows), to=(0, 0))


def bg_inner(border, bg):
    return bg


class _ThinBar(tk.Frame):
    """A slim progress bar (ttk's clam bar ignores thickness)."""
    def __init__(self, master, height):
        super().__init__(master, height=height, bd=0, highlightthickness=0)
        self.fill = tk.Frame(self, bd=0, highlightthickness=0)
        self._v = 0.0

    def colors(self, track, fill):
        self.configure(bg=track)
        self.fill.configure(bg=fill)

    def __setitem__(self, key, value):
        if key == "value":
            self._v = max(0.0, min(100.0, float(value)))
            if self._v <= 0:
                self.fill.place_forget()
            else:
                self.fill.place(x=0, y=0, relheight=1, relwidth=self._v / 100.0)
        else:
            super().__setitem__(key, value)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.cfg = load_config()
        if self.cfg.get("format") not in FORMAT_VALUES:
            self.cfg["format"] = "best"
        self.lang = self.cfg.get("lang", "en") if self.cfg.get("lang") in STR else "en"
        self.dark = bool(self.cfg.get("dark", True))
        self.scale = max(1.0, self.winfo_fpixels("1i") / 96.0)

        self.msg_q = queue.Queue()
        self.executor = None
        self.running = False
        self.cancel_ev = threading.Event()
        self.jobs = []          # list of dicts: url, iid, status, path, title
        self.batch = []         # job ids in the current run
        self.done = 0
        self.fracs = {}
        self._cards = []
        self._seg_q = []
        self._seg_c = []

        self.title("ClipFetch")
        self._init_fonts()
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        cs = self.px(16)
        self._chk_size = cs
        self._chk_off = tk.PhotoImage(width=cs, height=cs)
        self._chk_on = tk.PhotoImage(width=cs, height=cs)
        self.style.element_create("Card.check", "image", self._chk_off,
                                  ("selected", self._chk_on), width=cs + self.px(9), sticky="w")
        self.style.layout("Card.TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
            ("Card.check", {"side": "left", "sticky": ""}),
            ("Checkbutton.label", {"side": "left", "sticky": "nswe"})]})])

        geo = self.cfg.get("geometry") or ""
        self.geometry(geo if geo else f"{self.px(1060)}x{self.px(700)}")
        self.minsize(self.px(880), self.px(600))

        self._build_ui()
        self._retext()
        self._apply_theme()
        self._check_cookiefile()
        self._refresh_empty()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind_all("<Control-Return>", lambda e: self._start_or_cancel())
        self.bind_all("<Control-l>", lambda e: self.txt.focus_set())
        self.bind_all("<F1>", lambda e: self._show_help())
        self.after(100, self._drain_queue)
        self.deiconify()
        self.after(50, self._dark_titlebar)
        if not FFMPEG_DIR:
            self.after(400, self._setup_deps)   # first launch: fetch ffmpeg automatically

    # ---- basics ----
    def px(self, n):
        return int(round(n * self.scale))

    def L(self, key):
        return STR[self.lang][key]

    def _init_fonts(self):
        fams = set(tkfont.families(self))
        ui = "Segoe UI Variable Text" if "Segoe UI Variable Text" in fams else "Segoe UI"
        semi = "Segoe UI Semibold" if "Segoe UI Semibold" in fams else ui
        mono = "Cascadia Mono" if "Cascadia Mono" in fams else "Consolas"
        self.f_body = tkfont.Font(self, family=ui, size=10)
        self.f_small = tkfont.Font(self, family=ui, size=9)
        self.f_section = tkfont.Font(self, family=semi, size=10)
        self.f_head = tkfont.Font(self, family=semi, size=9)
        self.f_title = tkfont.Font(self, family=semi, size=15)
        self.f_button = tkfont.Font(self, family=semi, size=10)
        self.f_mono = tkfont.Font(self, family=mono, size=9)

    def _dark_titlebar(self):
        if os.name != "nt":
            return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            val = ctypes.c_int(1 if self.dark else 0)
            for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new, old)
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)) == 0:
                    break
        except Exception:
            pass

    def _card(self, parent):
        f = tk.Frame(parent, bd=0, highlightthickness=1)
        self._cards.append(f)
        return f

    # ---- layout ----
    def _build_ui(self):
        P = self.px
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Header
        hdr = ttk.Frame(self, style="Bg.TFrame", padding=(P(20), P(14), P(14), P(12)))
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.columnconfigure(2, weight=1)
        self.icon_img = _app_icon(64)
        self.iconphoto(True, self.icon_img)
        self.logo_img = self.icon_img.subsample(2, 2)
        ttk.Label(hdr, image=self.logo_img, style="Bg.TLabel").grid(row=0, column=0, padx=(0, P(10)))
        ttk.Label(hdr, text="ClipFetch", style="Title.TLabel").grid(row=0, column=1, sticky="w")
        self.lbl_tagline = ttk.Label(hdr, style="Muted.TLabel")
        self.lbl_tagline.grid(row=0, column=2, sticky="w", padx=(P(10), 0), pady=(P(4), 0))
        hr = ttk.Frame(hdr, style="Bg.TFrame")
        hr.grid(row=0, column=3, sticky="e")
        self.btn_lang = ttk.Button(hr, style="Ghost.TButton", command=self._toggle_lang, takefocus=0)
        self.btn_theme = ttk.Button(hr, style="Ghost.TButton", command=self._toggle_theme, takefocus=0)
        self.btn_setup = ttk.Button(hr, style="Ghost.TButton", command=self._setup_deps, takefocus=0)
        self.btn_help = ttk.Button(hr, style="Ghost.TButton", command=self._show_help, takefocus=0)
        for b in (self.btn_lang, self.btn_theme, self.btn_setup, self.btn_help):
            b.pack(side="left", padx=(P(2), 0))

        # Body
        body = ttk.Frame(self, style="Bg.TFrame", padding=(P(20), 0, P(20), 0))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        # -- Links card
        cl = self._card(body)
        cl.grid(row=0, column=0, sticky="ew", pady=(0, P(12)))
        cl.columnconfigure(0, weight=1)
        top = ttk.Frame(cl, style="Card.TFrame", padding=(P(16), P(12), P(10), P(8)))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)
        self.lbl_links = ttk.Label(top, style="Section.TLabel")
        self.lbl_links.grid(row=0, column=0, sticky="w")
        self.lbl_count = ttk.Label(top, style="CardMuted.TLabel")
        self.lbl_count.grid(row=0, column=1, sticky="w", padx=(P(8), 0))
        self.btn_paste = ttk.Button(top, style="CardGhost.TButton", command=self._paste, takefocus=0)
        self.btn_paste.grid(row=0, column=2)
        self.btn_clear = ttk.Button(top, style="CardGhost.TButton", command=self._clear_links, takefocus=0)
        self.btn_clear.grid(row=0, column=3, padx=(P(2), 0))
        wrap = ttk.Frame(cl, style="Card.TFrame", padding=(P(16), 0, P(16), P(16)))
        wrap.grid(row=1, column=0, sticky="ew")
        wrap.columnconfigure(0, weight=1)
        self.txt = tk.Text(wrap, height=5, wrap="none", bd=0, relief="flat", undo=True,
                           highlightthickness=1, padx=P(12), pady=P(10), font=self.f_body)
        self.txt.grid(row=0, column=0, sticky="ew")
        self.ph = tk.Label(self.txt, justify="left", anchor="nw", font=self.f_body, bd=0)
        self.ph.place(x=P(12), y=P(10))
        self.ph.bind("<Button-1>", lambda e: self.txt.focus_set())
        self.txt.bind("<<Modified>>", self._on_links_changed)

        # -- Queue card
        cq = self._card(body)
        cq.grid(row=1, column=0, sticky="nsew")
        cq.columnconfigure(0, weight=1)
        cq.rowconfigure(1, weight=1)
        qtop = ttk.Frame(cq, style="Card.TFrame", padding=(P(12), P(10), P(10), P(6)))
        qtop.grid(row=0, column=0, sticky="ew")
        qtop.columnconfigure(2, weight=1)
        self.tab = tk.StringVar(value="queue")
        self.rb_queue = ttk.Radiobutton(qtop, variable=self.tab, value="queue",
                                        style="Tab.Toolbutton", command=self._show_tab, takefocus=0)
        self.rb_log = ttk.Radiobutton(qtop, variable=self.tab, value="log",
                                      style="Tab.Toolbutton", command=self._show_tab, takefocus=0)
        self.rb_queue.grid(row=0, column=0)
        self.rb_log.grid(row=0, column=1, padx=(P(2), 0))
        self.lbl_qsum = ttk.Label(qtop, style="CardMuted.TLabel")
        self.lbl_qsum.grid(row=0, column=2, sticky="e", padx=(0, P(8)))
        self.btn_retry = ttk.Button(qtop, style="CardGhost.TButton", command=self._retry_failed, takefocus=0)
        self.btn_retry.grid(row=0, column=3)
        self.btn_retry.grid_remove()

        stack = ttk.Frame(cq, style="Card.TFrame", padding=(P(1), 0, P(1), P(1)))
        stack.grid(row=1, column=0, sticky="nsew")
        stack.columnconfigure(0, weight=1)
        stack.rowconfigure(0, weight=1)

        self.tree_frame = ttk.Frame(stack, style="Card.TFrame")
        self.tree_frame.grid(row=0, column=0, sticky="nsew")
        self.tree_frame.columnconfigure(0, weight=1)
        self.tree_frame.rowconfigure(0, weight=1)
        cols = ("name", "status", "progress", "detail")
        self.tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings", selectmode="extended")
        self.tree.column("name", width=P(250), minwidth=P(140), stretch=True, anchor="w")
        self.tree.column("status", width=P(120), minwidth=P(90), stretch=False, anchor="w")
        self.tree.column("progress", width=P(76), minwidth=P(64), stretch=False, anchor="e")
        self.tree.column("detail", width=P(340), minwidth=P(120), stretch=True, anchor="w")
        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.lbl_empty = ttk.Label(self.tree_frame, style="CardMuted.TLabel", justify="center")
        self.tree.bind("<Double-1>", self._on_row_double)
        self.tree.bind("<Button-3>", self._on_row_menu)
        self.tree.bind("<Delete>", lambda e: self._remove_selected())
        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)

        self.log_frame = ttk.Frame(stack, style="Card.TFrame")
        self.log_frame.grid(row=0, column=0, sticky="nsew")
        self.log_frame.columnconfigure(0, weight=1)
        self.log_frame.rowconfigure(0, weight=1)
        self.log = tk.Text(self.log_frame, state="disabled", wrap="word", bd=0, relief="flat",
                           highlightthickness=0, padx=P(14), pady=P(10), font=self.f_mono)
        lsb = ttk.Scrollbar(self.log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=lsb.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        lsb.grid(row=0, column=1, sticky="ns")
        self._show_tab()

        self.menu = tk.Menu(self, tearoff=0, bd=0, relief="flat")

        # -- Settings sidebar
        side = self._card(body)
        side.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(P(12), 0))
        sp = ttk.Frame(side, style="Card.TFrame", padding=(P(18), P(14), P(18), P(18)))
        sp.pack(fill="both", expand=True)
        sp.columnconfigure(0, weight=1)
        sp.configure(width=P(300))

        r = 0
        self.lbl_saveto = ttk.Label(sp, style="Field.TLabel")
        self.lbl_saveto.grid(row=r, column=0, sticky="w", pady=(0, P(5))); r += 1
        fr = ttk.Frame(sp, style="Card.TFrame")
        fr.grid(row=r, column=0, sticky="ew"); r += 1
        fr.columnconfigure(0, weight=1)
        self.outdir = tk.StringVar(value=self.cfg.get("outdir", DEFAULTS["outdir"]))
        ttk.Entry(fr, textvariable=self.outdir, width=22).grid(row=0, column=0, sticky="ew")
        ttk.Button(fr, text="…", style="Square.TButton", command=self._pick_dir,
                   takefocus=0).grid(row=0, column=1, padx=(P(6), 0), sticky="ns")

        self.lbl_quality = ttk.Label(sp, style="Field.TLabel")
        self.lbl_quality.grid(row=r, column=0, sticky="w", pady=(P(16), P(5))); r += 1
        seg = ttk.Frame(sp, style="Card.TFrame")
        seg.grid(row=r, column=0, sticky="ew"); r += 1
        self.fmt = tk.StringVar(value=self.cfg.get("format", "best"))
        for i, v in enumerate(FORMAT_VALUES):
            seg.columnconfigure(i, weight=1, uniform="q")
            b = ttk.Radiobutton(seg, variable=self.fmt, value=v, style="Seg.Toolbutton", takefocus=0,
                                command=self._sync_fix_state)
            b.grid(row=0, column=i, sticky="ew")
            self._seg_q.append(b)

        cr = ttk.Frame(sp, style="Card.TFrame")
        cr.grid(row=r, column=0, sticky="ew", pady=(P(16), 0)); r += 1
        cr.columnconfigure(0, weight=1)
        self.lbl_conc = ttk.Label(cr, style="Card.TLabel")
        self.lbl_conc.grid(row=0, column=0, sticky="w")
        self.conc = tk.IntVar(value=int(self.cfg.get("conc", 3)))
        ttk.Spinbox(cr, from_=1, to=8, width=4, textvariable=self.conc,
                    state="readonly").grid(row=0, column=1, sticky="e")

        self.fix = tk.BooleanVar(value=bool(self.cfg.get("fix", True)))
        self.archive = tk.BooleanVar(value=bool(self.cfg.get("archive", False)))
        self.notify = tk.BooleanVar(value=bool(self.cfg.get("notify", True)))
        self.chk_fix = ttk.Checkbutton(sp, variable=self.fix, style="Card.TCheckbutton")
        self.chk_archive = ttk.Checkbutton(sp, variable=self.archive, style="Card.TCheckbutton")
        self.chk_notify = ttk.Checkbutton(sp, variable=self.notify, style="Card.TCheckbutton")
        self.chk_fix.grid(row=r, column=0, sticky="w", pady=(P(12), 0)); r += 1
        self.chk_archive.grid(row=r, column=0, sticky="w", pady=(P(6), 0)); r += 1
        self.chk_notify.grid(row=r, column=0, sticky="w", pady=(P(6), 0)); r += 1

        ttk.Separator(sp).grid(row=r, column=0, sticky="ew", pady=(P(18), P(14))); r += 1

        self.lbl_signin = ttk.Label(sp, style="Section.TLabel")
        self.lbl_signin.grid(row=r, column=0, sticky="w"); r += 1
        self.lbl_signin_hint = ttk.Label(sp, style="CardMuted.TLabel", wraplength=P(260))
        self.lbl_signin_hint.grid(row=r, column=0, sticky="w", pady=(P(2), P(8))); r += 1
        cseg = ttk.Frame(sp, style="Card.TFrame")
        cseg.grid(row=r, column=0, sticky="ew"); r += 1
        self.cookie_mode = tk.IntVar(value=int(self.cfg.get("cookie_mode", 0)))
        for i in range(3):
            cseg.columnconfigure(i, weight=1, uniform="c")
            b = ttk.Radiobutton(cseg, variable=self.cookie_mode, value=i, style="Seg.Toolbutton",
                                takefocus=0, command=self._on_cookie_mode)
            b.grid(row=0, column=i, sticky="ew")
            self._seg_c.append(b)

        self.cookie_box = ttk.Frame(sp, style="Card.TFrame")
        self.cookie_box.grid(row=r, column=0, sticky="ew", pady=(P(10), 0)); r += 1
        self.cookie_box.columnconfigure(0, weight=1)
        self.browser = tk.StringVar(value=self.cfg.get("browser", "chrome"))
        self.cb_browser = ttk.Combobox(self.cookie_box, textvariable=self.browser, state="readonly",
                                       values=list(BROWSER_EXE.keys()))
        self.file_row = ttk.Frame(self.cookie_box, style="Card.TFrame")
        self.file_row.columnconfigure(0, weight=1)
        self.cookiefile = tk.StringVar(value=self.cfg.get("cookiefile", ""))
        self.ent_cookiefile = ttk.Entry(self.file_row, textvariable=self.cookiefile, width=18)
        self.ent_cookiefile.grid(row=0, column=0, sticky="ew")
        self.btn_pickfile = ttk.Button(self.file_row, style="CardBtn.TButton",
                                       command=self._pick_cookiefile, takefocus=0)
        self.btn_pickfile.grid(row=0, column=1, padx=(P(6), 0), sticky="ns")
        self.lbl_cf_status = ttk.Label(self.cookie_box, style="CardMuted.TLabel")
        self.cookiefile.trace_add("write", self._check_cookiefile)
        sp.rowconfigure(r, weight=1)

        # Footer
        foot = ttk.Frame(self, style="Bg.TFrame", padding=(P(20), P(14), P(20), P(18)))
        foot.grid(row=2, column=0, sticky="ew")
        foot.columnconfigure(0, weight=1)
        self.progress = _ThinBar(foot, P(4))
        self.progress.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, P(12)))
        self.status = tk.StringVar(value="")
        self.lbl_statustext = ttk.Label(foot, textvariable=self.status, style="Muted.TLabel")
        self.lbl_statustext.grid(row=1, column=0, sticky="w")
        self.btn_open = ttk.Button(foot, style="TButton", command=self._open_dir)
        self.btn_open.grid(row=1, column=1, padx=(0, P(8)))
        self.btn = ttk.Button(foot, style="Accent.TButton", command=self._start_or_cancel)
        self.btn.grid(row=1, column=2)

        self._sync_cookie_state()
        self._sync_fix_state()

    # ---- theme ----
    def _apply_theme(self):
        c = PALETTE["dark" if self.dark else "light"]
        self.c = c
        P = self.px
        s = self.style
        s.configure(".", background=c["bg"], foreground=c["text"], fieldbackground=c["raised"],
                    bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"],
                    troughcolor=c["raised"], selectbackground=c["select"],
                    selectforeground=c["text"], insertcolor=c["text"], font=self.f_body,
                    focuscolor=c["accent"])
        for name, bg in (("Bg", c["bg"]), ("Card", c["surface"])):
            s.configure(f"{name}.TFrame", background=bg)
            s.configure(f"{name}.TLabel", background=bg, foreground=c["text"])
        s.configure("TFrame", background=c["bg"])
        s.configure("TLabel", background=c["bg"], foreground=c["text"])
        s.configure("Title.TLabel", background=c["bg"], foreground=c["text"], font=self.f_title)
        s.configure("Muted.TLabel", background=c["bg"], foreground=c["muted"], font=self.f_small)
        s.configure("CardMuted.TLabel", background=c["surface"], foreground=c["muted"], font=self.f_small)
        s.configure("Section.TLabel", background=c["surface"], foreground=c["text"], font=self.f_section)
        s.configure("Field.TLabel", background=c["surface"], foreground=c["muted"], font=self.f_head)
        s.configure("Status.TLabel", background=c["surface"], font=self.f_small)

        def button(name, bg, fg, hover, fg_hover=None, border=None, pad=(14, 7), font=None, width=0):
            border = border or bg
            s.configure(name, background=bg, foreground=fg, bordercolor=border, width=width,
                        lightcolor=bg, darkcolor=bg, relief="flat", focusthickness=0,
                        focuscolor=bg, padding=(P(pad[0]), P(pad[1])), anchor="center",
                        font=font or self.f_body)
            s.map(name,
                  background=[("disabled", bg), ("pressed", hover), ("active", hover)],
                  lightcolor=[("pressed", hover), ("active", hover)],
                  darkcolor=[("pressed", hover), ("active", hover)],
                  bordercolor=[("active", border if border != bg else hover)],
                  foreground=[("disabled", c["subtle"]), ("active", fg_hover or fg)])

        button("TButton", c["raised"], c["text"], c["hover"], border=c["border"])
        button("CardBtn.TButton", c["raised"], c["text"], c["hover"], border=c["border"], pad=(12, 5))
        button("Square.TButton", c["raised"], c["text"], c["hover"], border=c["border"], pad=(10, 5))
        button("Ghost.TButton", c["bg"], c["muted"], c["hover"], fg_hover=c["text"], pad=(10, 5))
        button("CardGhost.TButton", c["surface"], c["muted"], c["hover"], fg_hover=c["text"], pad=(10, 4))
        button("Accent.TButton", c["accent"], c["on_accent"], c["accent_hover"],
               pad=(22, 8), font=self.f_button, width=-10)
        button("Danger.TButton", c["raised"], c["danger"], c["hover"], border=c["border"],
               pad=(22, 8), font=self.f_button, width=-10)

        # segmented control + tabs
        s.configure("Seg.Toolbutton", background=c["raised"], foreground=c["muted"],
                    bordercolor=c["border"], lightcolor=c["raised"], darkcolor=c["raised"],
                    padding=(P(6), P(6)), anchor="center", relief="flat", focusthickness=0,
                    focuscolor=c["raised"], font=self.f_body)
        s.map("Seg.Toolbutton",
              background=[("selected", c["select"]), ("active", c["hover"])],
              lightcolor=[("selected", c["select"]), ("active", c["hover"])],
              darkcolor=[("selected", c["select"]), ("active", c["hover"])],
              bordercolor=[("selected", c["accent"])],
              foreground=[("selected", c["seg_fg"]), ("active", c["text"])])
        s.configure("Tab.Toolbutton", background=c["surface"], foreground=c["muted"],
                    bordercolor=c["surface"], lightcolor=c["surface"], darkcolor=c["surface"],
                    padding=(P(10), P(4)), relief="flat", focusthickness=0,
                    focuscolor=c["surface"], font=self.f_section)
        s.map("Tab.Toolbutton",
              background=[("selected", c["raised"]), ("active", c["raised"])],
              lightcolor=[("selected", c["raised"]), ("active", c["raised"])],
              darkcolor=[("selected", c["raised"]), ("active", c["raised"])],
              bordercolor=[("selected", c["raised"]), ("active", c["raised"])],
              foreground=[("selected", c["text"]), ("active", c["text"])])

        # inputs
        field = dict(fieldbackground=c["raised"], foreground=c["text"], bordercolor=c["border"],
                     lightcolor=c["raised"], darkcolor=c["raised"], insertcolor=c["text"],
                     padding=(P(8), P(5)), arrowcolor=c["muted"], background=c["raised"],
                     selectbackground=c["select"], selectforeground=c["text"])
        focus = dict(bordercolor=[("focus", c["accent"])],
                     lightcolor=[("focus", c["raised"])], darkcolor=[("focus", c["raised"])],
                     fieldbackground=[("disabled", c["surface"]), ("readonly", c["raised"])],
                     foreground=[("disabled", c["subtle"])],
                     arrowcolor=[("disabled", c["subtle"]), ("active", c["text"])],
                     background=[("active", c["hover"])],
                     selectbackground=[("readonly", c["raised"])],
                     selectforeground=[("readonly", c["text"])])
        for name in ("TEntry", "TCombobox", "TSpinbox"):
            s.configure(name, **field)
            s.map(name, **focus)
        self.option_add("*TCombobox*Listbox.background", c["surface"])
        self.option_add("*TCombobox*Listbox.foreground", c["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", c["select"])
        self.option_add("*TCombobox*Listbox.selectForeground", c["text"])
        self.option_add("*TCombobox*Listbox.font", self.f_body)
        self.option_add("*TCombobox*Listbox.borderWidth", 0)

        s.configure("Card.TCheckbutton", background=c["surface"], foreground=c["text"],
                    indicatorbackground=c["raised"], indicatorforeground=c["on_accent"],
                    upperbordercolor=c["border"], lowerbordercolor=c["border"],
                    indicatormargin=(0, 0, P(8), 0), focusthickness=0, focuscolor=c["surface"])
        s.map("Card.TCheckbutton",
              background=[("active", c["surface"])],
              indicatorbackground=[("selected", c["accent"]), ("active", c["hover"])],
              upperbordercolor=[("selected", c["accent"])],
              lowerbordercolor=[("selected", c["accent"])],
              foreground=[("disabled", c["subtle"])])

        s.configure("Treeview", background=c["surface"], fieldbackground=c["surface"],
                    foreground=c["text"], bordercolor=c["surface"], lightcolor=c["surface"],
                    darkcolor=c["surface"], rowheight=P(32), borderwidth=0, font=self.f_body)
        s.map("Treeview", background=[("selected", c["select"])],
              foreground=[("selected", c["text"])])
        s.configure("Treeview.Heading", background=c["surface"], foreground=c["muted"],
                    bordercolor=c["border"], lightcolor=c["surface"], darkcolor=c["surface"],
                    relief="flat", font=self.f_head, padding=(P(10), P(7)))
        s.map("Treeview.Heading", background=[("active", c["surface"])],
              foreground=[("active", c["text"])])
        self.tree.tag_configure("muted", foreground=c["muted"])
        self.tree.tag_configure("active", foreground=c["text"])
        self.tree.tag_configure("done", foreground=c["text"])
        self.tree.tag_configure("failed", foreground=c["danger"])

        s.configure("Thin.Horizontal.TProgressbar", troughcolor=c["raised"], background=c["accent"],
                    bordercolor=c["raised"], lightcolor=c["accent"], darkcolor=c["accent"],
                    thickness=P(4))
        s.configure("Vertical.TScrollbar", background=c["raised"], troughcolor=c["surface"],
                    bordercolor=c["surface"], lightcolor=c["raised"], darkcolor=c["raised"],
                    arrowcolor=c["muted"], gripcount=0, arrowsize=P(11))
        s.map("Vertical.TScrollbar", background=[("active", c["hover"])])
        s.configure("TSeparator", background=c["border"])

        _draw_check(self._chk_off, self._chk_size, self.scale, c["surface"], c["subtle"], None, None)
        _draw_check(self._chk_on, self._chk_size, self.scale, c["surface"], None, c["accent"], "#ffffff")
        self.configure(bg=c["bg"])
        self.progress.colors(c["raised"], c["accent"])
        for f in self._cards:
            f.configure(bg=c["surface"], highlightbackground=c["border"], highlightcolor=c["border"])
        self.txt.configure(bg=c["raised"], fg=c["text"], insertbackground=c["text"],
                           selectbackground=c["select"], selectforeground=c["text"],
                           highlightbackground=c["border"], highlightcolor=c["accent"])
        self.ph.configure(bg=c["raised"], fg=c["subtle"])
        self.log.configure(bg=c["surface"], fg=c["text"], insertbackground=c["text"],
                           selectbackground=c["select"])
        self.log.tag_configure("time", foreground=c["subtle"])
        self.log.tag_configure("err", foreground=c["danger"])
        self.menu.configure(bg=c["surface"], fg=c["text"], activebackground=c["select"],
                            activeforeground=c["text"], disabledforeground=c["subtle"],
                            font=self.f_body)
        self.btn_theme.configure(text=self.L("theme_to_light" if self.dark else "theme_to_dark"))
        self._check_cookiefile()
        self._dark_titlebar()

    def _toggle_theme(self):
        self.dark = not self.dark
        self._apply_theme()

    def _toggle_lang(self):
        self.lang = "tr" if self.lang == "en" else "en"
        self._retext()
        self._check_cookiefile()

    # ---- text ----
    def _retext(self):
        L = self.L
        self.lbl_tagline.configure(text=L("tagline"))
        self.btn_lang.configure(text=L("lang_switch"))
        self.btn_theme.configure(text=L("theme_to_light" if self.dark else "theme_to_dark"))
        self.btn_setup.configure(text=L("setup"))
        self.btn_help.configure(text=L("help"))
        self.lbl_links.configure(text=L("links"))
        self.btn_paste.configure(text=L("paste"))
        self.btn_clear.configure(text=L("clear"))
        self.ph.configure(text=L("placeholder"))
        self.rb_queue.configure(text=L("tab_queue"))
        self.rb_log.configure(text=L("tab_log"))
        self.btn_retry.configure(text=L("retry_failed"))
        for col in ("name", "status", "progress", "detail"):
            self.tree.heading(col, text=L("col_" + col), anchor="e" if col == "progress" else "w")
        self.lbl_empty.configure(text=L("empty_queue"))
        self.lbl_saveto.configure(text=L("save_to"))
        self.lbl_quality.configure(text=L("quality"))
        for b, t in zip(self._seg_q, L("q_labels")):
            b.configure(text=t)
        self.lbl_conc.configure(text=L("conc"))
        self.chk_fix.configure(text=L("fix"))
        self.chk_archive.configure(text=L("archive"))
        self.chk_notify.configure(text=L("notify"))
        self.lbl_signin.configure(text=L("signin"))
        self.lbl_signin_hint.configure(text=L("signin_hint"))
        for b, t in zip(self._seg_c, L("cookie_opts")):
            b.configure(text=t)
        self.btn_pickfile.configure(text=L("choose"))
        self.btn_open.configure(text=L("openfolder"))
        self._set_main_button()
        self._update_count()
        for job in self.jobs:
            if job.get("iid") and self.tree.exists(job["iid"]):
                self.tree.set(job["iid"], "status", L("st_" + job["status"]))
        self._update_summary()
        if not self.running:
            self._idle_status()

    def _idle_status(self):
        ff = self.L("ffmpeg_ok") if FFMPEG_DIR else self.L("ffmpeg_warn")
        self.status.set(f"{self.L('ready')}  ·  {ff}")

    def _set_main_button(self):
        if self.running:
            txt = self.L("cancelling") if self.cancel_ev.is_set() else self.L("cancel")
            self.btn.configure(text=txt, style="Danger.TButton",
                               state="disabled" if self.cancel_ev.is_set() else "normal")
        else:
            self.btn.configure(text=self.L("download"), style="Accent.TButton", state="normal")

    # ---- links box ----
    def _on_links_changed(self, _e=None):
        self.txt.edit_modified(False)
        self._update_count()

    def _update_count(self):
        raw = self.txt.get("1.0", "end").strip()
        if raw:
            self.ph.place_forget()
        else:
            self.ph.place(x=self.px(12), y=self.px(10))
        n = len(extract_urls(raw))
        key = "count_zero" if n == 0 else ("count_one" if n == 1 else "count")
        self.lbl_count.configure(text=self.L(key).format(n=n))

    def _paste(self):
        try:
            data = self.clipboard_get()
        except Exception:
            data = ""
        urls = extract_urls(data)
        if not urls:
            self.status.set(self.L("clip_empty"))
            return
        have = set(extract_urls(self.txt.get("1.0", "end")))
        new = [u for u in urls if u not in have]
        if new:
            cur = self.txt.get("1.0", "end").rstrip("\n")
            self.txt.insert("end", ("\n" if cur.strip() else "") + "\n".join(new))
            self.txt.see("end")
        self._update_count()

    def _clear_links(self):
        self.txt.delete("1.0", "end")
        self._update_count()
        self.txt.focus_set()

    # ---- cookies ----
    def _on_cookie_mode(self):
        self._sync_cookie_state()
        self._check_cookiefile()

    def _sync_cookie_state(self):
        m = self.cookie_mode.get()
        self.cb_browser.grid_forget()
        self.file_row.grid_forget()
        self.lbl_cf_status.grid_forget()
        if m == 1:
            self.cb_browser.grid(row=0, column=0, sticky="ew")
        elif m == 2:
            self.file_row.grid(row=0, column=0, sticky="ew")
            self.lbl_cf_status.grid(row=1, column=0, sticky="w", pady=(self.px(8), 0))

    def _check_cookiefile(self, *_):
        if not hasattr(self, "c") or self.cookie_mode.get() != 2:
            return
        p = self.cookiefile.get()
        if not p or not os.path.isfile(p):
            txt, col = self.L("cf_none"), self.c["muted"]
        elif cookiefile_has_instagram_login(p):
            txt, col = self.L("cf_ok"), self.c["success"]
        else:
            txt, col = self.L("cf_nologin"), self.c["danger"]
        self.lbl_cf_status.configure(text="●  " + txt, foreground=col)

    def _sync_fix_state(self):
        self.chk_fix.configure(state="disabled" if self.fmt.get() == "mp3" else "normal")

    # ---- small helpers ----
    def _pick_dir(self):
        d = filedialog.askdirectory(initialdir=self.outdir.get() or ".")
        if d:
            self.outdir.set(d)

    def _pick_cookiefile(self):
        f = filedialog.askopenfilename(filetypes=[("cookies.txt", "*.txt"), ("All files", "*.*")])
        if f:
            self.cookiefile.set(f)

    def _open_dir(self):
        d = self.outdir.get()
        if os.path.isdir(d):
            os.startfile(d)
        else:
            messagebox.showinfo(self.L("info"), self.L("folder_not_yet"))

    def _show_tab(self):
        if self.tab.get() == "log":
            self.log_frame.tkraise()
        else:
            self.tree_frame.tkraise()

    def _logline(self, s, err=False):
        self.log.configure(state="normal")
        self.log.insert("end", time.strftime("%H:%M:%S") + "  ", "time")
        self.log.insert("end", s + "\n", "err" if err else ())
        self.log.see("end")
        self.log.configure(state="disabled")

    def _refresh_empty(self):
        if self.tree.get_children():
            self.lbl_empty.place_forget()
        else:
            self.lbl_empty.place(relx=0.5, rely=0.55, anchor="center")

    def _update_summary(self):
        counts = {}
        for j in self.jobs:
            counts[j["status"]] = counts.get(j["status"], 0) + 1
        ok, fail = counts.get("done", 0), counts.get("failed", 0) + counts.get("cancelled", 0)
        if not self.jobs:
            self.lbl_qsum.configure(text="")
        elif fail:
            self.lbl_qsum.configure(text=self.L("finished").format(ok=ok, fail=fail))
        else:
            self.lbl_qsum.configure(text=self.L("finished_ok").format(ok=ok))
        if fail and not self.running:
            self.btn_retry.grid()
        else:
            self.btn_retry.grid_remove()

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
            "fix": bool(self.fix.get()),
            "dark": bool(self.dark),
            "geometry": self.geometry(),
        }

    def _on_close(self):
        self.cancel_ev.set()
        save_config(self._collect_cfg())
        self.destroy()

    def _setup_deps(self):
        self.btn_setup.configure(state="disabled")
        self.status.set(self.L("setup_running"))
        self._logline(self.L("setup_running"))

        def work():
            ensure_ytdlp(lambda s: self.msg_q.put(("log", s)))
            ok = ensure_ffmpeg(lambda s: self.msg_q.put(("log", s)))
            msg = self.L("setup_ok") if ok else self.L("setup_ffmpeg_fail")
            self.msg_q.put(("log", msg))
            self.msg_q.put(("status", msg))
            self.msg_q.put(("enable_setup", None))

        threading.Thread(target=work, daemon=True).start()

    def _show_help(self):
        c = self.c
        P = self.px
        win = tk.Toplevel(self)
        win.title(self.L("help_title"))
        win.geometry(f"{P(620)}x{P(600)}")
        win.configure(bg=c["surface"])
        win.transient(self)
        frame = tk.Frame(win, bg=c["surface"])
        frame.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(frame)
        sb.pack(side="right", fill="y")
        txt = tk.Text(frame, wrap="word", bg=c["surface"], fg=c["text"], bd=0, relief="flat",
                      highlightthickness=0, padx=P(28), pady=P(22), font=self.f_body,
                      spacing1=P(2), spacing3=P(2), yscrollcommand=sb.set,
                      selectbackground=c["select"])
        txt.pack(fill="both", expand=True)
        sb.configure(command=txt.yview)
        txt.tag_configure("h", font=self.f_section, foreground=c["text"], spacing1=P(14), spacing3=P(4))
        txt.tag_configure("p", foreground=c["muted"], lmargin1=0, lmargin2=0)
        txt.tag_configure("code", font=self.f_mono, foreground=c["text"])
        blocks = self.L("help_text").strip().split("\n\n")
        for block in blocks:
            lines = block.split("\n")
            txt.insert("end", lines[0] + "\n", "h")
            for line in lines[1:]:
                tag = "code" if line.startswith("  ") else "p"
                txt.insert("end", line + "\n", tag)
        txt.configure(state="disabled")
        win.bind("<Escape>", lambda e: win.destroy())
        try:
            import ctypes
            win.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
            val = ctypes.c_int(1 if self.dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), 4)
        except Exception:
            pass

    # ---- queue rows ----
    def _row_set(self, job_id, **fields):
        job = self.jobs[job_id]
        iid = job["iid"]
        if not self.tree.exists(iid):
            return
        if "status" in fields:
            job["status"] = fields["status"]
            self.tree.set(iid, "status", self.L("st_" + fields["status"]))
            self.tree.item(iid, tags=(STATUS_TAG.get(fields["status"], "active"),))
        if "title" in fields and fields["title"]:
            job["title"] = fields["title"]
            self.tree.set(iid, "name", fields["title"])
        if "progress" in fields:
            self.tree.set(iid, "progress", fields["progress"])
        if "detail" in fields:
            self.tree.set(iid, "detail", fields["detail"])
        if "path" in fields and fields["path"]:
            job["path"] = fields["path"]

    def _selected_jobs(self):
        sel = set(self.tree.selection())
        return [i for i, j in enumerate(self.jobs) if j["iid"] in sel]

    def _on_row_select(self, _e=None):
        ids = self._selected_jobs()
        if len(ids) == 1:
            j = self.jobs[ids[0]]
            detail = self.tree.set(j["iid"], "detail")
            self.status.set(detail or j["url"])

    def _on_row_double(self, e):
        iid = self.tree.identify_row(e.y)
        for j in self.jobs:
            if j["iid"] == iid and j.get("path") and os.path.exists(j["path"]):
                os.startfile(j["path"])
                return

    def _on_row_menu(self, e):
        iid = self.tree.identify_row(e.y)
        if not iid:
            return
        if iid not in self.tree.selection():
            self.tree.selection_set(iid)
        ids = self._selected_jobs()
        if not ids:
            return
        first = self.jobs[ids[0]]
        has_file = bool(first.get("path")) and os.path.exists(first.get("path", ""))
        m = self.menu
        m.delete(0, "end")
        m.add_command(label=self.L("menu_open"), state="normal" if has_file else "disabled",
                      command=lambda: os.startfile(first["path"]))
        m.add_command(label=self.L("menu_show"), state="normal" if has_file else "disabled",
                      command=lambda: subprocess.Popen(["explorer", "/select,", os.path.normpath(first["path"])]))
        m.add_command(label=self.L("menu_copy"), command=lambda: self._copy_links(ids))
        m.add_separator()
        idle = "disabled" if self.running else "normal"
        m.add_command(label=self.L("menu_retry"), state=idle, command=lambda: self._run_jobs(ids))
        m.add_command(label=self.L("menu_remove"), state=idle, command=self._remove_selected)
        m.tk_popup(e.x_root, e.y_root)

    def _copy_links(self, ids):
        self.clipboard_clear()
        self.clipboard_append("\n".join(self.jobs[i]["url"] for i in ids))

    def _remove_selected(self):
        if self.running:
            return
        sel = set(self.tree.selection())
        for iid in sel:
            self.tree.delete(iid)
        self.jobs = [j for j in self.jobs if j["iid"] not in sel]
        self._refresh_empty()
        self._update_summary()

    def _retry_failed(self):
        ids = [i for i, j in enumerate(self.jobs) if j["status"] in ("failed", "cancelled")]
        if ids:
            self._run_jobs(ids)

    # ---- queue processing ----
    def _drain_queue(self):
        try:
            while True:
                kind, payload = self.msg_q.get_nowait()
                if kind == "log":
                    self._logline(payload)
                elif kind == "err":
                    self._logline(payload, err=True)
                elif kind == "status":
                    self.status.set(payload)
                elif kind == "row":
                    job_id, fields = payload
                    self._row_set(job_id, **fields)
                elif kind == "frac":
                    job_id, f = payload
                    self.fracs[job_id] = f
                    self._update_progress()
                elif kind == "enable_setup":
                    self.btn_setup.configure(state="normal")
                elif kind == "done_one":
                    self.done += 1
                    self.fracs[payload] = 1.0
                    self._update_progress()
                    self.status.set(self.L("running").format(d=self.done, t=len(self.batch)))
                    self._update_summary()
                    if self.done >= len(self.batch):
                        self._finish()
        except queue.Empty:
            pass
        self.after(100, self._drain_queue)

    def _update_progress(self):
        if self.batch:
            pct = min(100.0, sum(self.fracs.values()) / len(self.batch) * 100.0)
            self.progress["value"] = pct

    def _start_or_cancel(self):
        if self.running:
            self.cancel_ev.set()
            self._set_main_button()
        else:
            self._start()

    def _preflight(self, urls):
        if self.cookie_mode.get() == 2 and not os.path.isfile(self.cookiefile.get()):
            messagebox.showwarning(self.L("warn"), self.L("need_cookiefile"))
            return False
        if (self.cookie_mode.get() == 2
                and any("instagram.com" in u for u in urls)
                and not cookiefile_has_instagram_login(self.cookiefile.get())):
            if not messagebox.askyesno(self.L("ig_title"), self.L("ig_no_login")):
                return False
        if self.cookie_mode.get() == 1:
            exe = BROWSER_EXE.get(self.browser.get(), "")
            if exe and is_process_running(exe):
                if not messagebox.askyesno(self.L("preflight_title"),
                                           self.L("preflight_msg").format(b=self.browser.get())):
                    return False
        return True

    def _start(self):
        urls = extract_urls(self.txt.get("1.0", "end"))
        if not urls:
            messagebox.showwarning(self.L("warn"), self.L("no_links"))
            return
        if not self._preflight(urls):
            return
        # a fresh batch replaces finished rows from the previous one
        for j in self.jobs:
            if self.tree.exists(j["iid"]):
                self.tree.delete(j["iid"])
        self.jobs = []
        for u in urls:
            iid = self.tree.insert("", "end", values=(short_url(u), "", "", ""))
            self.jobs.append({"url": u, "iid": iid, "status": "queued", "path": "", "title": ""})
        self.txt.delete("1.0", "end")
        self._update_count()
        self._run_jobs(list(range(len(self.jobs))))

    def _run_jobs(self, ids):
        if self.running or not ids:
            return
        if not self._preflight([self.jobs[i]["url"] for i in ids]):
            return
        outdir = self.outdir.get().strip()
        os.makedirs(outdir, exist_ok=True)
        save_config(self._collect_cfg())

        self.running = True
        self.cancel_ev.clear()
        self.batch = list(ids)
        self.done = 0
        self.fracs = {i: 0.0 for i in ids}
        self.progress["value"] = 0
        for i in ids:
            self._row_set(i, status="queued", progress="", detail="")
        self.tab.set("queue")
        self._show_tab()
        self._refresh_empty()
        self._set_main_button()
        self._update_summary()
        self._logline(self.L("started").format(n=len(ids)))
        self.status.set(self.L("running").format(d=0, t=len(ids)))

        fmt = self.fmt.get()
        cmode = self.cookie_mode.get()
        browser = self.browser.get()
        cfile = self.cookiefile.get()
        archive = bool(self.archive.get())
        fix = bool(self.fix.get())
        conc = max(1, min(8, int(self.conc.get())))
        put = self.msg_q.put

        def worker(job_id, url):
            row = lambda **f: put(("row", (job_id, f)))
            if self.cancel_ev.is_set():
                row(status="cancelled", progress="")
                put(("done_one", job_id))
                return
            got_path = []
            row(status="downloading", progress="0%")

            def on_start(info):
                row(title=info.get("title"))

            def on_done(info):
                got_path.append(info.get("filepath") or info.get("_filename") or "")
                row(title=info.get("title"))

            def hook(d):
                if self.cancel_ev.is_set():
                    raise yt_dlp.utils.DownloadCancelled()
                info = d.get("info_dict") or {}
                if d["status"] == "downloading":
                    tot = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    dl = d.get("downloaded_bytes") or 0
                    frac = (dl / tot) if tot else 0
                    put(("frac", (job_id, frac)))
                    spd = (d.get("_speed_str") or "").strip()
                    eta = (d.get("_eta_str") or "").strip()
                    detail = "  ·  ".join(x for x in (spd, ("ETA " + eta) if eta and eta != "Unknown" else "") if x)
                    row(status="downloading", progress=f"{frac * 100:.0f}%", detail=detail,
                        title=info.get("title"))
                elif d["status"] == "finished":
                    put(("frac", (job_id, 1.0)))
                    row(status="processing", progress="100%", detail="", title=info.get("title"))

            def report(status, vcodec, acodec):
                txt = self.L("pp_" + status).format(v=vcodec or "?", a=acodec or self.L("no_audio"))
                if status == "recoding":
                    row(status="converting", detail=txt)
                else:
                    row(detail=txt)
                put(("log", f"#{job_id + 1}  {txt}"))

            logger = _ErrorLogger(lambda m: put(("err", f"#{job_id + 1}  {m}")))
            opts = build_opts(fmt, outdir, cmode, browser, cfile, hook, archive)
            opts["logger"] = logger
            put(("log", f"#{job_id + 1}  {url}"))
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    if fmt != "mp3" and fix:
                        ydl.add_post_processor(PremierePP(report), when="after_move")
                    ydl.add_post_processor(_InfoPP(on_start), when="before_dl")
                    ydl.add_post_processor(_InfoPP(on_done), when="after_move")
                    code = ydl.download([url])
                if self.cancel_ev.is_set() and code != 0:
                    row(status="cancelled", progress="")
                elif code == 0:
                    path = got_path[-1] if got_path else ""
                    fields = {"status": "done", "progress": "100%", "path": path}
                    if not path:
                        fields["detail"] = self.L("skipped")
                    elif not (fmt != "mp3" and fix):
                        fields["detail"] = os.path.basename(path)
                    row(**fields)
                else:
                    msg = logger.last or "yt-dlp error"
                    hint = cookie_error_hint(self, msg, cmode, browser)
                    row(status="failed", progress="", detail=hint or msg)
            except yt_dlp.utils.DownloadCancelled:
                row(status="cancelled", progress="", detail="")
            except Exception as e:
                hint = cookie_error_hint(self, str(e), cmode, browser)
                row(status="failed", progress="", detail=hint or str(e))
                put(("err", f"#{job_id + 1}  {e}"))
            finally:
                put(("done_one", job_id))

        self.executor = ThreadPoolExecutor(max_workers=conc)
        for i in ids:
            self.executor.submit(worker, i, self.jobs[i]["url"])

    def _finish(self):
        self.running = False
        if self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None
        self.progress["value"] = 100
        self._set_main_button()
        self._update_summary()
        ok = sum(1 for i in self.batch if self.jobs[i]["status"] == "done")
        fail = len(self.batch) - ok
        msg = (self.L("finished").format(ok=ok, fail=fail) if fail
               else self.L("finished_ok").format(ok=ok))
        self.status.set(msg)
        self._logline(msg)
        if self.notify.get() and not self.cancel_ev.is_set():
            self.bell()
            if os.name == "nt" and self.focus_displayof() is None:
                try:
                    import ctypes
                    ctypes.windll.user32.FlashWindow(ctypes.windll.user32.GetParent(self.winfo_id()), True)
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# CLI (terminal) mode
# ---------------------------------------------------------------------------
def run_cli(argv=None):
    p = argparse.ArgumentParser(
        prog="ClipFetch.exe" if FROZEN else "clipfetch.py",
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
        print("Updating yt-dlp...")
        ensure_ytdlp(print)
        print("Checking ffmpeg...")
        ok = ensure_ffmpeg(print)
        print("Setup complete." if ok else "ffmpeg could not be installed.")
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
        print("ffmpeg is missing, installing it...")
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
                print("  ERROR (code %s)" % code)
        except Exception as e:
            print("  ERROR:", e)
    print("Done: %d/%d" % (ok_count, len(args.urls)))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.stdout is None:          # windowed .exe started from a terminal
            try:
                import ctypes
                ctypes.windll.kernel32.AttachConsole(-1)
                sys.stdout = sys.stderr = open("CONOUT$", "w", encoding="utf-8")
            except Exception:
                sys.stdout = sys.stderr = open(os.devnull, "w")
        run_cli()
    else:
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ClipFetch")
            except Exception:
                pass
        App().mainloop()
