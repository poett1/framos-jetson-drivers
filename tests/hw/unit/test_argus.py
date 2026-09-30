import pytest

from lib.argus import daemon_errors, parse_fps, pipeline, tuning_file

pytestmark = pytest.mark.unit


def _msg(rendered, current, average):
    return ("/GstPipeline:pipeline0/GstFPSDisplaySink:fpsdisplaysink0: last-message = "
            f"rendered: {rendered}, dropped: 0, current: {current:.2f}, average: {average:.2f}\n")


def test_parse_fps_is_median_of_current_after_warmup():
    # startup burst: the cumulative average overestimates (seen on hardware: 74.1 for 72)
    t = _msg(40, 150.0, 150.0) + _msg(80, 90.0, 110.0) + _msg(116, 72.1, 94.0) + \
        "".join(_msg(116 + 36 * i, 72.0 + (i % 3 - 1) * 0.1, 80.0) for i in range(1, 12))
    assert parse_fps(t) == pytest.approx(72.0, abs=0.11)


def test_parse_fps_short_run_falls_back_to_all_values():
    assert parse_fps(_msg(10, 71.0, 70.0) + _msg(20, 72.0, 71.0)) == pytest.approx(71.5)
    assert parse_fps("nothing") is None


def test_daemon_errors():
    log = "ok line\nSCF: Error BadParameter: knobSetId 5 not found\nNvCameraIspGetNitoPathIfEnabled() returned error\n"
    assert daemon_errors(log) == ["SCF: Error BadParameter: knobSetId 5 not found",
                                  "NvCameraIspGetNitoPathIfEnabled() returned error"]


def test_pipeline_caps():
    cmd = " ".join(pipeline({"sensor_mode": 5, "width": 2064, "height": 1552, "max_fps": 117.0}))
    assert "sensor-mode=5" in cmd and "width=2064,height=1552,framerate=117/1" in cmd
    assert "fpsdisplaysink" in cmd and "sync=false" in cmd
    assert "num-buffers=702" in cmd   # about 6 s at 117 fps, enough intervals after warm-up


def test_tuning_file(tmp_path):
    prof = {"badge": "imx900_rear_framos", "argus_tuning": "nito"}
    assert tuning_file(prof, tmp_path) == tmp_path / "imx900_rear_framos.nito"
    prof["argus_tuning"] = "isp"
    assert tuning_file(prof, tmp_path) == tmp_path / "camera_overrides.isp"


def test_failure_report_has_output_tail_and_daemon_errors():
    from lib.argus import failure_report
    out = "\n".join(f"line {i}" for i in range(100)) + "\nERROR: from element nvarguscamerasrc0\n"
    rep = failure_report("no frames", out, ["SCF: Error Timeout: Sending critical error event"])
    assert rep.startswith("no frames")
    assert "ERROR: from element nvarguscamerasrc0" in rep and "line 0\n" not in rep
    assert "nvargus-daemon:\nSCF: Error Timeout: Sending critical error event" in rep
