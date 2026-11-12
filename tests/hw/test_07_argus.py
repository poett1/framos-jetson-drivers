"""Argus capture (nvarguscamerasrc) per Argus mode: rate, daemon errors.

Jetpack 7.2 needs <badge>.nito (argus_tuning: nito); Jetpack 6 uses the
camera_overrides.isp override if present (argus_tuning: isp). The VIC clock is pinned
at its maximum during the capture (fixture vic_max)."""

import subprocess

import pytest

from lib.argus import (daemon_errors, failure_report, parse_fps, pipeline, sensor_modes,
                       tuning_file)

pytestmark = pytest.mark.argus


def test_argus_rate(profile, sensor, argus_mode, vic_max, argus_daemon, record_property):
    tuning = tuning_file(profile)
    record_property("tuning", tuning.name if tuning.exists() else "none")
    record_property("vic_mhz", vic_max)
    if profile["argus_tuning"] == "nito" and not tuning.exists():
        pytest.skip(f"no {tuning}")
    try:
        r = subprocess.run(pipeline(argus_mode), capture_output=True, text=True, timeout=60)
        out = r.stdout + r.stderr
    except subprocess.TimeoutExpired as e:
        out = "".join(x.decode(errors="replace") if isinstance(x, bytes) else (x or "")
                      for x in (e.stdout, e.stderr))
        pytest.fail(failure_report("nvarguscamerasrc did not finish within 60 s", out,
                                   daemon_errors(argus_daemon())))
    fps = parse_fps(out)
    errors = daemon_errors(argus_daemon())
    record_property("fps", fps)
    modes = sensor_modes(out)
    n = argus_mode["sensor_mode"]
    assert n < len(modes) and modes[n] == (argus_mode["width"], argus_mode["height"]), \
        f"Argus sensor mode {n} is {modes[n] if n < len(modes) else 'missing'}, " \
        f"not {argus_mode['width']}x{argus_mode['height']} (DT mode order)"
    assert fps is not None, failure_report("no frames from nvarguscamerasrc", out, errors)
    assert fps == pytest.approx(argus_mode["max_fps"], rel=profile["stream"]["rate_tolerance"])
    assert errors == [], failure_report("nvargus-daemon reported errors", out, errors)
