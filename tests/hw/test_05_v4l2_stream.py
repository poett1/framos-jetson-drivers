"""Raw V4L2 streaming per mode at its maximum rate: rate, sequence gaps, CSI errors."""

import pytest

from lib.v4l2 import StreamTimeout, get_ctrls, parse_stream, rate_stats, set_ctrl, stream

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


def test_mode_switch_starts_at_mode_default_rate(profile, sensor, v4l2_mode, dmesg_mark,
                                                  record_property):
    """Without setting frame_rate, a stream right after another mode runs at its own
    default rate, not at the rate left from the previous mode. (Argus starts each
    session like this; a stale rate made 2064x1552 10-bit run at half rate.)"""
    out = stream(sensor.video, v4l2_mode, 250, {}, timeout=250 / 1.4 + 15)
    st = rate_stats(parse_stream(out), 150)
    record_property("fps", round(st.fps, 2))
    assert st.fps == pytest.approx(v4l2_mode["max_fps"], rel=profile["stream"]["rate_tolerance"])
    assert dmesg_mark() == []


def _other_mode(profile, mode):
    """The first V4L2 mode of the profile in another DT mode than `mode`."""
    key = lambda m: (m["pixelformat"], m["width"], m["height"])  # noqa: E731
    return next(m for m in profile["v4l2_modes"] if key(m) != key(mode))


def test_frame_rate_set_before_a_mode_switch_is_kept(profile, sensor, dmesg_mark,
                                                    record_property):
    """A frame_rate a V4L2 client sets between streams applies to the next stream,
    also when that stream is in another DT mode (the mode's default applies only
    when the value was left from the previous stream)."""
    first = profile["v4l2_modes"][0]
    stream(sensor.video, first, 20, {}, timeout=20)
    set_ctrl(sensor.video, "frame_rate", 30000000)
    out = stream(sensor.video, _other_mode(profile, first), 200, {}, timeout=200 / 25 + 15)
    st = rate_stats(parse_stream(out), 150)
    record_property("fps", round(st.fps, 2))
    assert st.fps == pytest.approx(30.0, rel=profile["stream"]["rate_tolerance"])
    assert dmesg_mark() == []


def test_mode_default_rate_survives_a_low_data_rate(profile, sensor, record_property):
    """A stream at a low data rate narrows the frame_rate range of its mode; that must
    not lower the mode's default rate for later streams at the full data rate."""
    full = profile["v4l2_modes"][0]
    before = get_ctrls(sensor.video, ["data_rate"])["data_rate"]
    set_ctrl(sensor.video, "data_rate", 4)  # 594 Mbps/lane, the lowest
    try:
        # the range is narrowed at stream start; frames need not arrive (on the AGX J5
        # direct connection the lower data rates deliver none)
        stream(sensor.video, full, 20, {}, timeout=8)
    except StreamTimeout:
        pass
    finally:
        set_ctrl(sensor.video, "data_rate", before)
    stream(sensor.video, _other_mode(profile, full), 20, {}, timeout=20)
    out = stream(sensor.video, full, 250, {}, timeout=250 / 25 + 15)
    st = rate_stats(parse_stream(out), 150)
    record_property("fps", round(st.fps, 2))
    assert st.fps == pytest.approx(full["max_fps"], rel=profile["stream"]["rate_tolerance"])


def test_mode_default_rate_after_a_format_change_narrowed_the_range(profile, sensor,
                                                                    record_property):
    """Setting a format narrows the frame_rate range to the mode's last range and clamps
    the value (here 117 to 72 fps). That is not a client's choice: the stream still
    starts at its DT default. Sequence: 12-bit full, twice 10-bit at another size,
    10-bit full."""
    full12, full10 = profile["v4l2_modes"][0], profile["v4l2_modes"][1]
    other10 = next(m for m in profile["v4l2_modes"] if m["pixelformat"] == full10["pixelformat"]
                   and (m["width"], m["height"]) != (full10["width"], full10["height"]))
    for mode in (full12, other10, other10):
        stream(sensor.video, mode, 20, {}, timeout=20)
    out = stream(sensor.video, full10, 250, {}, timeout=250 / 25 + 15)
    st = rate_stats(parse_stream(out), 150)
    record_property("fps", round(st.fps, 2))
    assert st.fps == pytest.approx(full10["max_fps"], rel=profile["stream"]["rate_tolerance"])
