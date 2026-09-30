"""Argus capture (nvarguscamerasrc) per Argus mode: rate, daemon errors.

Jetpack 7.2 needs <badge>.nito (argus_tuning: nito); Jetpack 6 uses the
camera_overrides.isp override if present (argus_tuning: isp)."""

import subprocess

import pytest

from lib.argus import daemon_errors, parse_fps, pipeline, tuning_file

pytestmark = pytest.mark.argus


def test_argus_rate(profile, sensor, argus_mode, argus_daemon, record_property):
    tuning = tuning_file(profile)
    record_property("tuning", tuning.name if tuning.exists() else "none")
    if profile["argus_tuning"] == "nito" and not tuning.exists():
        pytest.skip(f"no {tuning}")
    try:
        out = subprocess.run(pipeline(argus_mode), capture_output=True, text=True, timeout=60).stdout
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        pytest.fail("nvarguscamerasrc did not finish within 60 s:\n" + out[-2000:])
    fps = parse_fps(out)
    errors = daemon_errors(argus_daemon())
    record_property("fps", fps)
    assert fps is not None, "no frames from nvarguscamerasrc:\n" + out[-2000:]
    assert fps == pytest.approx(argus_mode["max_fps"], rel=profile["stream"]["rate_tolerance"])
    assert errors == [], "nvargus-daemon reported:\n" + "\n".join(errors[:20])
