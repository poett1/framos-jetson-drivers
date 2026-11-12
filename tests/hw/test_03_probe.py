"""Sensor probe (kernel log) and media graph."""

import subprocess

import pytest

from lib import kmsg, media

pytestmark = pytest.mark.probe


def test_probe_log(profile):
    devname = profile["devname"]
    log = "\n".join(kmsg.kernel_log())
    expected = [f"{devname}: probing v4l2 sensor",
                f"subdev {devname} bound",
                f"{devname}: Detected {devname.split()[0]} sensor"]
    missing = [line for line in expected if line not in log]
    assert not missing, f"not in the kernel log: {missing}"


def test_media_topology(profile, sensor, record_property):
    record_property("video", sensor.video)
    record_property("subdev", sensor.subdev)
    record_property("media", sensor.media)
    out = subprocess.run(["media-ctl", "-d", sensor.media, "-p"], capture_output=True, text=True).stdout
    assert media.topology_ok(media.parse_topology(out), profile["devname"]), \
        f"graph is not {profile['devname']} -> nvcsi -> vi-output:\n{out}"
