"""Frame reader that runs FFmpeg as a subprocess, one per camera.

OpenCV's FFmpeg backend serialises `VideoCapture` construction behind a single
global mutex. That is survivable when sources open in milliseconds, but the
hackathon portal trickles data — a measured **48 seconds** to produce the first
frame of one stream. Under a shared lock, ten such cameras cannot all be
opening at once: each waits for the one before it, the ingest budget never
fills, and cameras that are perfectly reachable look dead.

Running FFmpeg as a separate process per camera removes the shared lock
entirely: slow sources open in parallel, a stalled one cannot block its
neighbours, and each reader gets exactly the flags its source needs
(`-seekable 0` for the portal's non-faststart MP4 chunks, RTSP over TCP,
generous timeouts). Frames arrive as raw BGR24 on stdout, which is the same
array shape OpenCV would have handed back, so nothing downstream changes.

File sources keep using OpenCV: they open instantly, need seeking to loop, and
gain nothing from a subprocess.
"""

import logging
import shutil
import subprocess
import threading
from pathlib import Path

import numpy as np

log = logging.getLogger("sutra.ffreader")

_FFMPEG: str | None = None


def ffmpeg_path() -> str | None:
    """Locate ffmpeg once: PATH first, then the winget install location."""
    global _FFMPEG
    if _FFMPEG is None:
        found = shutil.which("ffmpeg")
        if not found:
            import os

            base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
            if base.is_dir():
                for cand in base.glob("Gyan.FFmpeg*/ffmpeg-*/bin/ffmpeg.exe"):
                    found = str(cand)
                    break
        _FFMPEG = found or ""
        log.info("ffmpeg: %s", _FFMPEG or "NOT FOUND — falling back to OpenCV capture")
    return _FFMPEG or None


# FFmpeg reports failures as a bare errno ("Error number -138 occurred") or as
# internal filter-graph wording. Neither means anything to a control-room
# operator deciding whether a camera needs a field visit, so the raw text is
# translated to a cause. Keys are matched as substrings, longest first.
#
# The numeric codes are MSVCRT errno values negated by AVERROR(): on Windows
# ETIMEDOUT is 138, not the 110 of glibc, which is why -138 shows up here.
_ERROR_MEANINGS: dict[str, str] = {
    "Error number -138": "connection timed out — the source accepted the request but sent no data",
    "Error number -110": "connection timed out — the source accepted the request but sent no data",
    "Nothing was written into output file": "connected, but the source sent no video packets",
    "Connection refused": "connection refused — nothing is listening at that address",
    "Server returned 401": "rejected by the source: credentials required",
    "Server returned 403": "rejected by the source: access forbidden",
    "Server returned 404": "the source URL no longer exists on the portal",
    "Server returned 5": "the source server reported an internal error",
    "Immediate exit requested": "decoder stopped",
    "Invalid data found": "the stream is arriving corrupted or in an unreadable format",
    "No route to host": "no network route to the camera",
    "Name or service not known": "the camera hostname does not resolve",
    "Protocol not found": "unsupported stream protocol for this source URL",
}


def explain_error(raw: str) -> str:
    """Plain-language cause for a raw FFmpeg stderr line.

    Unrecognised text is passed through: an operator seeing an unfamiliar
    message is better served than one seeing a message we silently swallowed.
    """
    if not raw:
        return ""
    for needle in sorted(_ERROR_MEANINGS, key=len, reverse=True):
        if needle in raw:
            return _ERROR_MEANINGS[needle]
    # strip FFmpeg's component prefix ("[out#0/rawvideo @ 0x...] ") — an address
    # in the middle of an operator-facing string is pure noise
    cleaned = raw.split("] ", 1)[-1] if raw.startswith("[") else raw
    return cleaned.strip()


class FFmpegFrameReader:
    """Pull decoded BGR frames from a source at a fixed rate.

    The output size is pinned so each frame is a known number of bytes; the
    source aspect ratio is preserved and padded rather than stretched, because
    a distorted plate is a plate the OCR will misread.
    """

    def __init__(self, url: str, width: int = 1920, height: int = 1080, fps: float = 1.0,
                 is_rtsp: bool = False, timeout_s: int = 90):
        self.url = url
        self.width = max(160, int(width) or 1920)
        self.height = max(120, int(height) or 1080)
        self.fps = fps
        self.is_rtsp = is_rtsp
        self.timeout_s = timeout_s
        self.proc: subprocess.Popen | None = None
        self._stderr_tail: list[str] = []

    @property
    def frame_bytes(self) -> int:
        return self.width * self.height * 3

    def start(self) -> bool:
        exe = ffmpeg_path()
        if not exe:
            return False
        scale = (
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2"
        )
        cmd = [exe, "-hide_banner", "-loglevel", "error", "-nostdin"]
        if self.is_rtsp:
            cmd += ["-rtsp_transport", "tcp"]
        else:
            # the portal's chunks are plain MP4 with the index at the end and a
            # server that mishandles the range requests FFmpeg would use to
            # reach it; parsing progressively is both correct and what works
            cmd += ["-seekable", "0", "-reconnect", "1", "-reconnect_streamed", "1",
                    "-reconnect_delay_max", "5"]
        cmd += [
            "-rw_timeout", str(self.timeout_s * 1_000_000),
            "-i", self.url,
            "-an", "-sn",
            "-vf", f"fps={self.fps},{scale}",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1",
        ]
        try:
            self.proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                bufsize=self.frame_bytes * 2,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            log.exception("could not spawn ffmpeg for %s", self.url)
            return False
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        return True

    def _drain_stderr(self) -> None:
        """Keep stderr flowing (a full pipe would deadlock FFmpeg) and keep the
        last few lines so failures can be reported instead of guessed at."""
        proc = self.proc
        if not proc or not proc.stderr:
            return
        for raw in iter(proc.stderr.readline, b""):
            line = raw.decode("utf-8", "replace").strip()
            if line:
                self._stderr_tail = (self._stderr_tail + [line])[-5:]

    def read(self) -> np.ndarray | None:
        """Next frame, or None when the stream ends or the process dies."""
        proc = self.proc
        if not proc or not proc.stdout:
            return None
        want = self.frame_bytes
        buf = bytearray()
        while len(buf) < want:
            chunk = proc.stdout.read(want - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        return np.frombuffer(bytes(buf), np.uint8).reshape((self.height, self.width, 3))

    @property
    def last_error(self) -> str:
        return explain_error(self._stderr_tail[-1]) if self._stderr_tail else ""

    @property
    def raw_error(self) -> str:
        """Untranslated FFmpeg output, for the log rather than the operator."""
        return self._stderr_tail[-1] if self._stderr_tail else ""

    def stop(self) -> None:
        proc, self.proc = self.proc, None
        if not proc:
            return
        try:
            proc.kill()
        except OSError:
            pass
        for stream in (proc.stdout, proc.stderr):
            try:
                if stream:
                    stream.close()
            except OSError:
                pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
