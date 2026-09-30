import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

HW_DIR = Path(__file__).resolve().parents[1]
PROFILE = HW_DIR / "profiles" / "agx-fpa4a-j5-direct-imx900-4lane.yaml"

STUB = '''
import pytest
from conftest import SESSION

RESULTS = {results!r}

@pytest.fixture(scope="session")
def compliance_results():
    SESSION["compliance"] = RESULTS
    return RESULTS
'''


@pytest.fixture
def suite(pytester):
    for name in ("conftest.py", "pytest.ini", "test_07_compliance.py"):
        shutil.copy(HW_DIR / name, pytester.path / name)
    shutil.copytree(HW_DIR / "lib", pytester.path / "lib")
    shutil.copy(PROFILE, pytester.path / PROFILE.name)
    return pytester


def _run(suite, results, *args):
    (suite.path / "test_07_compliance.py").write_text(
        (HW_DIR / "test_07_compliance.py").read_text() + STUB.format(results=results))
    return suite.runpytest_subprocess(f"--profile={PROFILE.name}", "-p", "no:cacheprovider",
                                      f"--results-dir={suite.path / 'res'}", *args)


RESULTS = {"video": {"VIDIOC_G/S_PARM": "FAIL", "VIDIOC_QUERYCAP": "OK"},
           "subdev": {"VIDIOC_SUBDEV_QUERYCAP": "OK"}, "media": {"MEDIA_IOC_G_TOPOLOGY": "FAIL"}}


def test_baseline_workflow(suite):
    baseline = suite.path / "compliance-baselines" / f"{PROFILE.stem}.txt"

    first = _run(suite, RESULTS, "--write-compliance-baseline")
    first.stdout.fnmatch_lines(["*no baseline*--write-compliance-baseline*"])
    assert baseline.read_text().splitlines()[-2:] == ["media: MEDIA_IOC_G_TOPOLOGY",
                                                      "video: VIDIOC_G/S_PARM"]

    second = _run(suite, RESULTS)
    second.assert_outcomes(passed=3, xfailed=2)

    fixed = {**RESULTS, "video": {"VIDIOC_G/S_PARM": "OK", "VIDIOC_QUERYCAP": "OK"}}
    third = _run(suite, fixed)
    third.assert_outcomes(passed=3, xfailed=1, failed=1)   # strict XPASS fails

    regressed = {**RESULTS, "subdev": {"VIDIOC_SUBDEV_QUERYCAP": "FAIL"}}
    fourth = _run(suite, regressed)
    fourth.assert_outcomes(passed=2, xfailed=2, failed=1)
    fourth.stdout.fnmatch_lines(["*new v4l2-compliance failures (subdev)*VIDIOC_SUBDEV_QUERYCAP*"])
