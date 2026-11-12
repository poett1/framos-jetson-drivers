import json
import shutil
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

HW_DIR = Path(__file__).resolve().parents[1]
JP6 = HW_DIR / "profiles" / "nano-p3768-cam1-direct-imx900-4lane-jp6.yaml"


@pytest.fixture
def suite(pytester):
    """A copy of the suite's conftest, pytest.ini and lib/ in a scratch dir."""
    for name in ("conftest.py", "pytest.ini"):
        shutil.copy(HW_DIR / name, pytester.path / name)
    shutil.copytree(HW_DIR / "lib", pytester.path / "lib")
    # the JP6 reference profile plus one declared known failure
    prof = yaml.safe_load(JP6.read_text())
    prof["known_failures"] = {"test_04_controls.py::test_defaults_after_boot": "starts at minimum"}
    prof["flaky"] = {"test_04_controls.py::test_sometimes": "intermittent CSI start"}
    (pytester.path / JP6.name).write_text(yaml.safe_dump(prof))
    pytester.makepyfile(test_04_controls="""
        import pytest

        def test_defaults_after_boot(profile):
            assert False, "starts at minimum"

        def test_frame_rate_64bit_roundtrip(profile, record_property):
            record_property("fps", 72.0)

        def test_needs_nito(profile):
            pytest.skip("no imx900_rear_framos.nito")

        @pytest.mark.unit
        def test_a_unit_test():
            pass

        def test_sometimes(profile):
            assert True   # a flaky test that passed this time: reported, not a failure
    """)
    return pytester


def test_known_failure_xfails_and_results_written(suite):
    res_dir = suite.path / "res"
    # "--opt=value": pytest takes a separate existing-path argument as a rootdir candidate
    result = suite.runpytest_subprocess(f"--profile={JP6.name}", f"--results-dir={res_dir}",
                                        "-p", "no:cacheprovider")
    result.assert_outcomes(passed=2, skipped=1, xfailed=1, xpassed=1)
    data = json.loads((res_dir / "results.json").read_text())
    outcomes = {r["nodeid"].split("::")[-1]: r["outcome"] for r in data["results"]}
    assert outcomes == {"test_defaults_after_boot": "xfailed",
                        "test_frame_rate_64bit_roundtrip": "passed",
                        "test_needs_nito": "skipped",
                        "test_sometimes": "xpassed"}
    summary = (res_dir / "summary.md").read_text()
    assert "test_a_unit_test" not in summary   # unit tests stay out of the hardware report
    assert "Profile: nano-p3768-cam1-direct-imx900-4lane-jp6" in summary
    assert "| test_frame_rate_64bit_roundtrip | PASS | fps=72.0 |" in summary
    assert "| test_needs_nito | SKIP | no imx900_rear_framos.nito |" in summary
    assert "| test_defaults_after_boot | XFAIL |" in summary


def test_without_profile_everything_skips(suite):
    result = suite.runpytest_subprocess("-p", "no:cacheprovider")
    result.assert_outcomes(skipped=4, passed=1)
    assert not (suite.path / "results").exists()


def test_bad_profile_is_usage_error(suite):
    (suite.path / "bad.yaml").write_text("name: x\n")
    result = suite.runpytest_subprocess("--profile=bad.yaml", "-p", "no:cacheprovider")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*bad.yaml*badge: missing*"])
