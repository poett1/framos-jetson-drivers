"""Raw frame content per mode: not all-zero, not constant (sanity, not image quality)."""

import pytest

from lib.v4l2 import capture_frame, frame_stats

pytestmark = pytest.mark.image


def test_frame_not_constant(profile, sensor, v4l2_mode, tmp_path, record_property):
    data = capture_frame(sensor.video, v4l2_mode, tmp_path / "frame.raw")
    mean, sd = frame_stats(data, v4l2_mode["pixelformat"])
    record_property("mean", round(mean, 1))
    record_property("stddev", round(sd, 1))
    assert sd > profile["image"]["min_stddev"], "frame is constant"
