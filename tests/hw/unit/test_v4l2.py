import subprocess
import time
from array import array

import pytest

from lib.v4l2 import (Frame, StreamTimeout, frame_stats, parse_ctrls, parse_stream,
                      rate_stats, stream)

pytestmark = pytest.mark.unit

MODE = {"name": "12-bit full", "pixelformat": "RG12", "width": 2064, "height": 1552, "max_fps": 72.0}


def _line(seq, ts):
    # format of v4l2-ctl 1.26 --stream-mmap --verbose
    return (f"cap dqbuf: {seq % 4} seq: {seq:6d} bytesused: 6406656 ts: {ts:.06f} "
            f"delta: 8.547 ms fps: 117.00 (ts-monotonic, ts-src-eof)")


def test_parse_stream_and_rate():
    text = "VIDIOC_STREAMON returned 0 (Success)\n" + "\n".join(
        _line(i, 100.0 + i / 117.0) for i in range(300))
    frames = parse_stream(text)
    st = rate_stats(frames, 300)
    assert st.frames == 300 and st.gaps == 0
    assert st.fps == pytest.approx(117.0, rel=1e-3)


def test_rate_uses_last_window():
    frames = [Frame(i, i / 72.0) for i in range(100)]
    frames += [Frame(100 + i, frames[-1].ts + (i + 1) / 117.0) for i in range(300)]
    assert rate_stats(frames, 300).fps == pytest.approx(117.0, rel=1e-3)


def test_gap_counted():
    frames = [Frame(0, 0.0), Frame(1, 0.01), Frame(3, 0.03)]
    assert rate_stats(frames, 3).gaps == 1


def test_too_few_frames_gives_zero_rate():
    assert rate_stats([Frame(0, 1.0)], 300).fps == 0.0


def test_parse_ctrls():
    out = "frame_rate: 72000000\nexposure: 10000\ngain: 0\n"
    assert parse_ctrls(out) == {"frame_rate": 72000000, "exposure": 10000, "gain": 0}


def test_frame_stats_constant_and_varied():
    assert frame_stats(bytes(2 * 2064 * 4), "RG12") == (0.0, 0.0)
    mean, sd = frame_stats(array("H", range(4096)).tobytes() * 3, "RG12")
    assert sd > 1.0
    mean8, sd8 = frame_stats(bytes(range(256)) * 50, "RGGB")
    assert sd8 > 1.0


def test_stream_timeout_kills_process():               # Review Focus 4
    t0 = time.monotonic()
    with pytest.raises(StreamTimeout):
        stream("/dev/null", MODE, 10, {}, timeout=1.0, cmd_prefix=["sleep", "37"])
    assert time.monotonic() - t0 < 5
    assert subprocess.run(["pgrep", "-f", "^sleep 37$"], capture_output=True).returncode == 1


def test_no_first_frame_times_out_before_setting_controls():
    t0 = time.monotonic()
    with pytest.raises(StreamTimeout, match="no frame"):
        stream("/dev/null", MODE, 10, {"frame_rate": 117000000}, timeout=1.0,
               cmd_prefix=["sleep", "38"])
    assert time.monotonic() - t0 < 5
    assert subprocess.run(["pgrep", "-f", "^sleep 38$"], capture_output=True).returncode == 1
