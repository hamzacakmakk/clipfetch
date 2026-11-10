"""Unit and integration tests for ClipFetch's non-GUI logic.

Run with:  python -m pytest
The conversion tests need ffmpeg/ffprobe on PATH and are skipped without them.
"""
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import clipfetch  # noqa: E402


# --- link extraction ----------------------------------------------------------

def test_extract_urls_from_messy_text():
    text = """Check these out:
    https://www.youtube.com/watch?v=jNQXAC9IVRw and also
    (https://www.tiktok.com/@user/video/123), https://x.com/a/status/9.
    https://www.youtube.com/watch?v=jNQXAC9IVRw  <- duplicate
    not a link: www.example.com"""
    assert clipfetch.extract_urls(text) == [
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "https://www.tiktok.com/@user/video/123",
        "https://x.com/a/status/9",
    ]


def test_extract_urls_empty():
    assert clipfetch.extract_urls("") == []
    assert clipfetch.extract_urls(None) == []
    assert clipfetch.extract_urls("no links here") == []


def test_short_url():
    assert clipfetch.short_url("https://www.youtube.com/watch?v=abc") == "youtube.com/watch?v=abc"
    long = "https://example.com/" + "a" * 200
    out = clipfetch.short_url(long, limit=30)
    assert len(out) == 30 and out.endswith("…")


# --- format selection -----------------------------------------------------------

def opts(fmt, **kw):
    args = dict(outdir="out", cookie_mode=0, browser="chrome", cookiefile="", hook=lambda d: None, archive=False)
    args.update(kw)
    return clipfetch.build_opts(fmt, args["outdir"], args["cookie_mode"], args["browser"],
                                args["cookiefile"], args["hook"], args["archive"])


def test_best_takes_highest_resolution_and_prefers_h264_at_equal_resolution():
    o = opts("best")
    assert o["format"] == "bv*+ba/b"
    assert o["format_sort"][0] == "res"                 # resolution first: 4K beats 1080p H.264
    assert "vcodec:h264" in o["format_sort"]            # then H.264 among equal resolutions
    assert o["format_sort"].index("res") < o["format_sort"].index("vcodec:h264")
    assert o["merge_output_format"] == "mp4"


@pytest.mark.parametrize("fmt,cap", [("1080", 1080), ("720", 720)])
def test_resolution_caps(fmt, cap):
    o = opts(fmt)
    assert f"[height<={cap}]" in o["format"]
    assert o["format_sort"][0] == f"res:{cap}"


def test_mp3_extracts_audio():
    o = opts("mp3")
    assert o["format"] == "ba/b"
    assert o["postprocessors"][0]["key"] == "FFmpegExtractAudio"
    assert o["postprocessors"][0]["preferredcodec"] == "mp3"


def test_archive_and_output_template(tmp_path):
    o = opts("best", outdir=str(tmp_path), archive=True)
    assert o["download_archive"] == os.path.join(str(tmp_path), "download_archive.txt")
    assert o["outtmpl"].startswith(str(tmp_path))
    assert o["noprogress"] and o["quiet"]


def test_cookie_modes(tmp_path):
    assert "cookiefile" not in opts("best") and "cookiesfrombrowser" not in opts("best")
    assert opts("best", cookie_mode=1, browser="firefox")["cookiesfrombrowser"] == ("firefox",)
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    assert opts("best", cookie_mode=2, cookiefile=str(cookies))["cookiefile"] == str(cookies)
    # a missing file is ignored instead of passed to yt-dlp
    assert "cookiefile" not in opts("best", cookie_mode=2, cookiefile=str(tmp_path / "missing.txt"))


# --- cookies ------------------------------------------------------------------------

def test_instagram_login_detection(tmp_path):
    good = tmp_path / "good.txt"
    good.write_text(".instagram.com\tTRUE\t/\tTRUE\t1999999999\tsessionid\tabc123\n")
    empty = tmp_path / "empty.txt"
    empty.write_text(".instagram.com\tTRUE\t/\tTRUE\t1999999999\tcsrftoken\txyz\n")
    assert clipfetch.cookiefile_has_instagram_login(str(good)) is True
    assert clipfetch.cookiefile_has_instagram_login(str(empty)) is False


class _FakeApp:
    def L(self, key):
        return key


@pytest.mark.parametrize("msg,mode,expected", [
    ("Failed to decrypt with DPAPI", 1, "hint_chrome_enc"),
    ("Could not copy Chrome cookie database", 1, "hint_browser_open"),
    ("cookie file is invalid", 2, "hint_cookiefile"),
    ("This content is not available. Login required", 0, "hint_login"),
    ("HTTP Error 404: Not Found", 0, ""),
])
def test_cookie_error_hints(msg, mode, expected):
    assert clipfetch.cookie_error_hint(_FakeApp(), msg, mode, "chrome") == expected


# --- video format checks -----------------------------------------------------------

@pytest.mark.parametrize("v,a,pix,cfr,ok", [
    ("h264", "aac", "yuv420p", True, True),
    ("h264", "", "yuv420p", True, True),        # silent video is fine
    ("vp9", "opus", "yuv420p", True, False),
    ("av1", "aac", "yuv420p", True, False),
    ("h264", "opus", "yuv420p", True, False),
    ("h264", "aac", "yuv420p10le", True, False),
    ("h264", "aac", "yuv420p", False, False),   # variable frame rate
])
def test_is_compat(v, a, pix, cfr, ok):
    assert clipfetch._is_compat(v, a, pix, cfr) is ok


def test_rate():
    assert clipfetch._rate("30000/1001") == pytest.approx(29.97, abs=0.01)
    assert clipfetch._rate("60/1") == 60
    assert clipfetch._rate("0/0") == 0
    assert clipfetch._rate("bad") == 0


# --- real conversion with ffmpeg -------------------------------------------------------

needs_ffmpeg = pytest.mark.skipif(
    not (clipfetch.FFMPEG_DIR or __import__("shutil").which("ffmpeg")),
    reason="ffmpeg not installed")


def _make_clip(path, vcodec, acodec):
    subprocess.run([clipfetch.FFMPEG, "-y", "-v", "error",
                    "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30:duration=2",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:v", vcodec, "-pix_fmt", "yuv420p", "-c:a", acodec, "-shortest", str(path)], check=True)


@needs_ffmpeg
def test_vp9_opus_is_converted_to_h264_aac(tmp_path):
    clip = tmp_path / "clip.mp4"
    _make_clip(clip, "libvpx-vp9", "libopus")
    assert clipfetch._probe_streams(str(clip))[:2] == ("vp9", "opus")
    events = []
    clipfetch.make_premiere_compatible(str(clip), lambda s, v, a: events.append(s))
    assert events == ["recoding", "done"]
    v, a, pix, cfr = clipfetch._probe_streams(str(clip))
    assert (v, a, pix, cfr) == ("h264", "aac", "yuv420p", True)
    assert not (tmp_path / "clip.premiere.mp4").exists()   # temp file cleaned up


@needs_ffmpeg
def test_compatible_file_is_left_untouched(tmp_path):
    clip = tmp_path / "ok.mp4"
    _make_clip(clip, "libx264", "aac")
    before = clip.stat().st_mtime_ns
    events = []
    clipfetch.make_premiere_compatible(str(clip), lambda s, v, a: events.append(s))
    assert events == ["already"]
    assert clip.stat().st_mtime_ns == before
