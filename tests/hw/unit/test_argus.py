import pytest

from lib.argus import daemon_errors, parse_fps, pipeline, tuning_file

pytestmark = pytest.mark.unit


def test_parse_fps_takes_last_average():
    t = ("/GstPipeline:pipeline0/GstFPSDisplaySink:fpsdisplaysink0: last-message = "
         "rendered: 10, dropped: 0, current: 70.10, average: 69.80\n"
         "/GstPipeline:pipeline0/GstFPSDisplaySink:fpsdisplaysink0: last-message = "
         "rendered: 300, dropped: 0, current: 72.00, average: 71.90\n")
    assert parse_fps(t) == pytest.approx(71.9)
    assert parse_fps("nothing") is None


def test_daemon_errors():
    log = "ok line\nSCF: Error BadParameter: knobSetId 5 not found\nNvCameraIspGetNitoPathIfEnabled() returned error\n"
    assert daemon_errors(log) == ["SCF: Error BadParameter: knobSetId 5 not found",
                                  "NvCameraIspGetNitoPathIfEnabled() returned error"]


def test_pipeline_caps():
    cmd = " ".join(pipeline({"sensor_mode": 5, "width": 2064, "height": 1552, "max_fps": 117.0}))
    assert "sensor-mode=5" in cmd and "width=2064,height=1552,framerate=117/1" in cmd
    assert "fpsdisplaysink" in cmd and "sync=false" in cmd


def test_tuning_file(tmp_path):
    prof = {"badge": "imx900_rear_framos", "argus_tuning": "nito"}
    assert tuning_file(prof, tmp_path) == tmp_path / "imx900_rear_framos.nito"
    prof["argus_tuning"] = "isp"
    assert tuning_file(prof, tmp_path) == tmp_path / "camera_overrides.isp"
