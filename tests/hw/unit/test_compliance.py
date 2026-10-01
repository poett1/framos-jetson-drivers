import pytest
from pathlib import Path

from lib.compliance import (BaselineMissing, NODES, failures, known_failure_params,
                            new_failures, parse, read_baseline, write_baseline)

pytestmark = pytest.mark.unit

# real output: v4l2-compliance 1.26.1 -m /dev/media0 on an AGX Orin without sensor
MEDIA0 = 'v4l2-compliance 1.26.1, 64 bits, 64-bit time_t\n\nCompliance test for tegra-camrtc-ca device /dev/media0:\n\nMedia Driver Info:\n\tDriver name      : tegra-camrtc-ca\n\tModel            : NVIDIA Tegra Video Input Device\n\tSerial           : \n\tBus info         : platform:tegra-capture-vi\n\tMedia version    : 6.8.12\n\tHardware revision: 0x00000003 (3)\n\tDriver version   : 6.8.12\n\nRequired ioctls:\n\ttest MEDIA_IOC_DEVICE_INFO: OK\n\ttest invalid ioctls: OK\n\nAllow for multiple opens:\n\ttest second /dev/media0 open: OK\n\ttest MEDIA_IOC_DEVICE_INFO: OK\n\ttest for unlimited opens: OK\n\nMedia Controller ioctls:\n\t\tfail: v4l2-test-media.cpp(121): !topology.num_entities\n\ttest MEDIA_IOC_G_TOPOLOGY: FAIL\n\ttest MEDIA_IOC_ENUM_ENTITIES/LINKS: OK\n\ttest MEDIA_IOC_SETUP_LINK: OK\n\nTotal for tegra-camrtc-ca device /dev/media0: 8, Succeeded: 7, Failed: 1, Warnings: 0\n\nGrand Total for tegra-camrtc-ca device /dev/media0: 8, Succeeded: 7, Failed: 1, Warnings: 0\n'

SAMPLE = """Compliance test for tegra-video device /dev/video0:
\ttest VIDIOC_QUERYCAP: OK
\ttest VIDIOC_G/S_PARM: OK (Not Supported)
\t\tfail: v4l2-test-formats.cpp(1034): ...
\ttest VIDIOC_TRY_FMT: FAIL
Total for tegra-video device /dev/video0: 3, Succeeded: 2, Failed: 1, Warnings: 0
"""


def test_nodes_use_media_only_flag():
    assert NODES == {"video": "-d", "subdev": "-u", "media": "-M"}


def test_parse_and_failures():
    r = parse(SAMPLE)
    assert r["VIDIOC_G/S_PARM"] == "OK (Not Supported)"
    assert failures(r) == ["VIDIOC_TRY_FMT"]


def test_parse_real_media_output():
    r = parse(MEDIA0)
    assert r["MEDIA_IOC_DEVICE_INFO"] == "OK"
    assert failures(r) == ["MEDIA_IOC_G_TOPOLOGY"]
    assert len(r) == 7   # 8 tests, one name twice


def test_repeated_name_fail_wins():
    r = parse("\ttest X: FAIL\n\ttest X: OK\n")
    assert r == {"X": "FAIL"}


def test_baseline_roundtrip(tmp_path):
    p = tmp_path / "b.txt"
    write_baseline(p, {"video": ["VIDIOC_TRY_FMT"], "media": []}, "# header")
    assert p.read_text().startswith("# header")
    assert read_baseline(p) == {"video": {"VIDIOC_TRY_FMT"}}


def test_baseline_comments_and_reasons(tmp_path):
    p = tmp_path / "b.txt"
    p.write_text("# c\n\nvideo: VIDIOC_G/S_PARM  # NVIDIA VI limitation\nmedia: MEDIA_IOC_G_TOPOLOGY\n")
    assert read_baseline(p) == {"video": {"VIDIOC_G/S_PARM"}, "media": {"MEDIA_IOC_G_TOPOLOGY"}}


def test_missing_baseline_reports_hint():          # Review Focus 5
    assert read_baseline(Path("/nonexistent/b.txt")) is None
    assert known_failure_params(None) == []           # collection still works
    with pytest.raises(BaselineMissing, match="--write-compliance-baseline"):
        new_failures("video", {"VIDIOC_TRY_FMT": "FAIL"}, None, Path("x.txt"))


def test_new_failures_against_baseline():
    base = {"video": {"VIDIOC_TRY_FMT"}}
    res = {"VIDIOC_TRY_FMT": "FAIL", "VIDIOC_S_FMT": "FAIL", "VIDIOC_QUERYCAP": "OK"}
    assert new_failures("video", res, base, Path("b.txt")) == ["VIDIOC_S_FMT"]


def test_known_failure_params_sorted():
    assert known_failure_params({"video": {"B", "A"}, "media": {"C"}}) == [
        ("media", "C"), ("video", "A"), ("video", "B")]


def test_run_summary_detects_a_run_that_tested_nothing():
    from lib.compliance import has_summary
    assert has_summary(SAMPLE)
    assert not has_summary("Failed to open /dev/video0: Device or resource busy\n")


def test_known_failure_with_missing_name_is_not_reported_as_fixed():
    from lib.compliance import known_failure_status
    with pytest.raises(LookupError):
        known_failure_status({"VIDIOC_QUERYCAP": "OK"}, "VIDIOC_TRY_FMT")
    assert known_failure_status({"VIDIOC_TRY_FMT": "FAIL"}, "VIDIOC_TRY_FMT") == "FAIL"
