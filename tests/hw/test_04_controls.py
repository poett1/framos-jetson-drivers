"""V4L2 controls: values after boot, 64-bit set and read back.

Runs before the streaming tests, which change the controls."""

import pytest

from lib.v4l2 import get_ctrls, set_ctrl

pytestmark = pytest.mark.controls


def test_defaults_after_boot(profile, sensor, record_property):
    defaults = profile["controls"]["defaults"]
    current = get_ctrls(sensor.video, list(defaults))
    for name, value in current.items():
        record_property(name, value)
    assert current == defaults, "control values after boot differ from the DT defaults " \
                                "(a second run without reboot sees the first run's values)"


def test_frame_rate_64bit_roundtrip(sensor):
    try:
        set_ctrl(sensor.video, "frame_rate", 60000000)
        assert get_ctrls(sensor.video, ["frame_rate"]) == {"frame_rate": 60000000}
    finally:
        set_ctrl(sensor.video, "frame_rate", 72000000)
