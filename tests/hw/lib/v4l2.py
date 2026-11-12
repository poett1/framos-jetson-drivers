"""V4L2 controls, raw streaming and frames via v4l2-ctl."""

import math
import re
import subprocess
import threading
from array import array
from dataclasses import dataclass

EIGHT_BIT = {"RGGB", "GRBG", "GBRG", "BA81", "GREY"}
DQBUF_RE = re.compile(r"cap dqbuf:\s*\d+\s+seq:\s*(\d+)\s+bytesused:.*?ts:\s*(\d+\.\d+)")


@dataclass
class Frame:
    seq: int
    ts: float


@dataclass
class StreamStats:
    fps: float
    gaps: int
    frames: int


class StreamTimeout(Exception):
    pass


CTRL_TIMEOUT = 10  # s, v4l2-ctl control calls
EXIT_TIMEOUT = 10  # s, for v4l2-ctl to exit after kill


def _fmt(mode):
    return (f"--set-fmt-video=width={mode['width']},height={mode['height']},"
            f"pixelformat={mode['pixelformat']}")


def parse_ctrls(text):
    ctrls = {}
    for line in text.splitlines():
        m = re.match(r"^\s*(\w+):\s*(-?\d+)(?:\s+\(.*\))?\s*$", line)
        if m:
            ctrls[m.group(1)] = int(m.group(2))
    return ctrls


def get_ctrls(dev, names):
    cmd = ["v4l2-ctl", "-d", dev] + [arg for n in names for arg in ("-C", n)]
    return parse_ctrls(subprocess.run(cmd, capture_output=True, text=True, check=True,
                                      timeout=CTRL_TIMEOUT).stdout)


def set_ctrl(dev, name, value):
    subprocess.run(["v4l2-ctl", "-d", dev, f"--set-ctrl={name}={value}"],
                   capture_output=True, text=True, check=True, timeout=CTRL_TIMEOUT)


def parse_stream(text):
    return [Frame(int(m.group(1)), float(m.group(2))) for m in DQBUF_RE.finditer(text)]


def rate_stats(frames, window):
    last = frames[-window:]
    if len(last) < 2 or last[-1].ts <= last[0].ts:
        return StreamStats(0.0, 0, len(last))
    fps = (len(last) - 1) / (last[-1].ts - last[0].ts)
    gaps = sum(1 for a, b in zip(last, last[1:]) if b.seq - a.seq != 1)
    return StreamStats(fps, gaps, len(last))


def stream(dev, mode, frames, ctrls_after_start, timeout, cmd_prefix=None):
    """Stream `frames` buffers; once the first frame arrived, set `ctrls_after_start`
    (control ranges follow the mode that streams). Returns the v4l2-ctl output.
    Raises StreamTimeout; the v4l2-ctl process never outlives the call."""
    cmd = cmd_prefix or ["v4l2-ctl", "-d", dev, _fmt(mode), "--stream-mmap",
                         f"--stream-count={frames}", "--stream-to=/dev/null", "--verbose"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lines, first = [], threading.Event()

    def reader():
        for line in proc.stdout:
            lines.append(line)
            if "dqbuf" in line:
                first.set()

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    try:
        if ctrls_after_start:
            if not first.wait(timeout):
                raise StreamTimeout(f"no frame within {timeout} s")
            for name, value in ctrls_after_start.items():
                set_ctrl(dev, name, value)
        try:
            proc.wait(timeout)
        except subprocess.TimeoutExpired:
            raise StreamTimeout(f"{frames} frames not done within {timeout} s")
    finally:
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(EXIT_TIMEOUT)
        except subprocess.TimeoutExpired:
            # stuck in the driver (D-state): report it instead of hanging the suite
            raise StreamTimeout(f"v4l2-ctl did not exit within {EXIT_TIMEOUT} s after kill "
                                "(stuck in the driver)") from None
        thread.join(2)
    return "".join(lines)


def capture_frame(dev, mode, path):
    """One raw frame after 10 skipped ones."""
    subprocess.run(["v4l2-ctl", "-d", dev, _fmt(mode), "--stream-mmap", "--stream-skip=10",
                    "--stream-count=1", f"--stream-to={path}"],
                   capture_output=True, text=True, check=True, timeout=30)
    return path.read_bytes()


def frame_stats(data, pixelformat):
    """(mean, standard deviation) over a sample of the pixels."""
    if pixelformat in EIGHT_BIT:
        pixels = array("B", data)
    else:
        pixels = array("H")
        pixels.frombytes(data[:len(data) - len(data) % 2])
    sample = pixels[::101]
    if not sample:
        return 0.0, 0.0
    mean = sum(sample) / len(sample)
    var = sum((p - mean) ** 2 for p in sample) / len(sample)
    return mean, math.sqrt(var)


CTRL_LINE_RE = re.compile(r"^\s*(\w+) 0x[0-9a-f]+ \(\w+\)\s*:(.*)$")


def parse_ctrl_list(text):
    """Writable scalar controls from `v4l2-ctl -l`: {name: value}. Read-only, payload
    (dims=) and execute-on-write controls are left out."""
    ctrls = {}
    for line in text.splitlines():
        m = CTRL_LINE_RE.match(line)
        if not m:
            continue
        rest = m.group(2)
        value = re.search(r"\bvalue=(-?\d+)", rest)
        if value is None or "dims=" in rest or re.search(r"read-only|execute-on-write", rest):
            continue
        ctrls[m.group(1)] = int(value.group(1))
    return ctrls


def snapshot_ctrls(dev):
    return parse_ctrl_list(subprocess.run(["v4l2-ctl", "-d", dev, "-l"], capture_output=True,
                                          text=True, check=True, timeout=CTRL_TIMEOUT).stdout)


def restore_ctrls(dev, snapshot, read=snapshot_ctrls, write=set_ctrl):
    """Set every control that differs from `snapshot` back; returns {name: (wanted, now)}
    for controls that still differ afterwards."""
    current = read(dev)
    for name, value in snapshot.items():
        if current.get(name) != value:
            try:
                write(dev, name, value)
            except subprocess.CalledProcessError:
                pass
    now = read(dev)
    return {n: (v, now.get(n)) for n, v in snapshot.items() if now.get(n) != v}
