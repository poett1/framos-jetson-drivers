"""Raw V4L2 streaming per mode at its maximum rate: rate, sequence gaps, CSI errors."""

import pytest

from lib.v4l2 import parse_stream, rate_stats, stream

pytestmark = pytest.mark.stream


def test_stream_rate(profile, sensor, v4l2_mode, dmesg_mark, record_property):
    s = profile["stream"]
    fps_ctrl = int(v4l2_mode["max_fps"] * 1e6)
    # the frame_rate range follows the streaming mode: set it once frames arrive
    out = stream(sensor.video, v4l2_mode, s["frames"], {"frame_rate": fps_ctrl},
                 timeout=s["frames"] / 36 + 15)
    st = rate_stats(parse_stream(out), s["window"])
    record_property("fps", round(st.fps, 2))
    record_property("gaps", st.gaps)
    errors = dmesg_mark()
    assert st.frames == s["window"], f"only {st.frames} frames parsed"
    assert st.fps == pytest.approx(v4l2_mode["max_fps"], rel=s["rate_tolerance"])
    assert st.gaps == 0, f"{st.gaps} sequence gaps"
    assert errors == [], "kernel reported capture errors:\n" + "\n".join(errors[:20])
