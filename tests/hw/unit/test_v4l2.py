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


# real v4l2-ctl -l after "v4l2-compliance -u": stock Jetpack 6.2.1 + FRAMOS l4t-r36.4.4, IMX900
CTRL_LIST = '\nCamera Controls\n\n                     group_hold 0x009a2003 (bool)   : default=0 value=0 flags=execute-on-write\n                    sensor_mode 0x009a2008 (int64)  : min=0 max=15 step=1 default=0 value=0 flags=slider\n                           gain 0x009a2009 (int64)  : min=0 max=480 step=1 default=0 value=0 flags=slider\n                       exposure 0x009a200a (int64)  : min=9 max=660000 step=1 default=10000 value=9 flags=update, slider\n                     frame_rate 0x009a200b (int64)  : min=1500000 max=72000000 step=1 default=72000000 value=1500000 flags=update, slider\n           sensor_configuration 0x009a2032 (u32)    : min=0 max=4294967295 step=1 default=0 dims=[22] flags=read-only, volatile, has-payload\n         sensor_mode_i2c_packet 0x009a2033 (u32)    : min=0 max=4294967295 step=1 default=0 dims=[1026] flags=read-only, volatile, has-payload\n      sensor_control_i2c_packet 0x009a2034 (u32)    : min=0 max=4294967295 step=1 default=0 dims=[1026] flags=read-only, volatile, has-payload\n                    bypass_mode 0x009a2064 (intmenu): min=0 max=1 default=0 value=0 (0 0x0)\n                override_enable 0x009a2065 (intmenu): min=0 max=1 default=0 value=0 (0 0x0)\n                   height_align 0x009a2066 (int)    : min=1 max=16 step=1 default=1 value=1\n                     size_align 0x009a2067 (intmenu): min=0 max=2 default=0 value=0 (1 0x1)\n               write_isp_format 0x009a2068 (int)    : min=1 max=1 step=1 default=1 value=1\n       sensor_signal_properties 0x009a2069 (u32)    : min=0 max=4294967295 step=1 default=0 dims=[30][18] flags=read-only, has-payload\n        sensor_image_properties 0x009a206a (u32)    : min=0 max=4294967295 step=1 default=0 dims=[30][16] flags=read-only, has-payload\n      sensor_control_properties 0x009a206b (u32)    : min=0 max=4294967295 step=1 default=0 dims=[30][36] flags=read-only, has-payload\n              sensor_dv_timings 0x009a206c (u32)    : min=0 max=4294967295 step=1 default=0 dims=[30][16] flags=read-only, has-payload\n               low_latency_mode 0x009a206d (bool)   : default=0 value=0\n               preferred_stride 0x009a206e (int)    : min=0 max=65535 step=1 default=0 value=0\n    override_capture_timeout_ms 0x009a206f (int)    : min=-1 max=2147483647 step=1 default=2500 value=2500\n                      data_rate 0x009a2078 (menu)   : min=0 max=4 default=0 value=4 (594 Mbps/lane)\n                   test_pattern 0x009a2079 (menu)   : min=0 max=5 default=0 value=5 (Color Bar Vertically)\n                 operation_mode 0x009a207a (menu)   : min=0 max=1 default=0 value=1 (Slave Mode)\n                    black_level 0x009a207d (int64)  : min=0 max=4095 step=1 default=240 value=240 flags=slider, execute-on-write\n                   sensor_modes 0x009a2082 (int)    : min=0 max=30 step=1 default=30 value=15 flags=read-only\n            global_shutter_mode 0x009a2083 (menu)   : min=0 max=2 default=0 value=0 (Normal Mode)\n                conversion_gain 0x009a2085 (bool)   : default=0 value=0 flags=update\n'


def test_parse_ctrl_list_writable_scalars_only():
    from lib.v4l2 import parse_ctrl_list
    ctrls = parse_ctrl_list(CTRL_LIST)
    assert ctrls["operation_mode"] == 1 and ctrls["data_rate"] == 4 and ctrls["test_pattern"] == 5
    assert ctrls["frame_rate"] == 1500000 and ctrls["bypass_mode"] == 0
    for skipped in ("sensor_configuration", "sensor_modes", "group_hold", "sensor_signal_properties"):
        assert skipped not in ctrls   # read-only, payload or execute-on-write


def test_restore_ctrls_sets_only_changed_and_reports_leftovers():
    from lib.v4l2 import restore_ctrls
    state = {"operation_mode": 1, "data_rate": 4, "gain": 0, "stuck": 7}
    written = []

    def write(dev, name, value):
        written.append((name, value))
        if name != "stuck":
            state[name] = value

    left = restore_ctrls("/dev/video0", {"operation_mode": 0, "data_rate": 0, "gain": 0, "stuck": 1},
                         read=lambda dev: dict(state), write=write)
    assert sorted(written) == [("data_rate", 0), ("operation_mode", 0), ("stuck", 1)]
    assert left == {"stuck": (1, 7)}


class _StuckProc:
    """A v4l2-ctl stuck in the driver (D-state): kill() has no effect, wait() never returns."""
    stdout = iter(())
    killed = False

    def poll(self):
        return None

    def kill(self):
        _StuckProc.killed = True

    def wait(self, timeout=None):
        if timeout is None:
            raise AssertionError("wait() without timeout would hang the suite")
        raise subprocess.TimeoutExpired("v4l2-ctl", timeout)


def test_stream_gives_up_on_a_process_stuck_in_the_driver(monkeypatch):   # Review Focus 4
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: _StuckProc())
    t0 = time.monotonic()
    with pytest.raises(StreamTimeout, match="did not exit"):
        stream("/dev/video0", MODE, 10, {}, timeout=0.5)
    assert _StuckProc.killed and time.monotonic() - t0 < 20


def test_control_calls_have_timeouts(monkeypatch):
    from lib import v4l2
    seen = []

    def fake_run(cmd, **kw):
        seen.append(kw.get("timeout"))
        return subprocess.CompletedProcess(cmd, 0, "frame_rate: 1\n", "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    v4l2.get_ctrls("/dev/video0", ["frame_rate"])
    v4l2.set_ctrl("/dev/video0", "frame_rate", 1)
    v4l2.snapshot_ctrls("/dev/video0")
    assert seen and all(t for t in seen)


def test_parse_ctrls_reads_menu_controls():
    from lib.v4l2 import parse_ctrls
    assert parse_ctrls("data_rate: 0 (2376 Mbps/lane)\nframe_rate: 72000000\n") == {
        "data_rate": 0, "frame_rate": 72000000}
