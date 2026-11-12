"""v4l2-compliance against the profile's baseline of accepted failures.

NVIDIA's VI driver fails parts of v4l2-compliance by design; the baseline
(compliance-baselines/<profile>.txt) lists them. New failures fail the run;
a baseline entry that starts passing fails too (strict xfail): remove it."""

import pytest

from conftest import SESSION
from lib import compliance

pytestmark = pytest.mark.compliance


@pytest.mark.parametrize("kind", list(compliance.NODES))
def test_no_new_failures(profile, compliance_results, kind, record_property):
    results = compliance_results[kind]
    if not results:
        out = SESSION.get("compliance_output", {}).get(kind, "")
        pytest.fail(f"v4l2-compliance reported no results ({kind}):\n" + out[-2000:])
    record_property("failed", len(compliance.failures(results)))
    record_property("tests", len(results))
    path = compliance.baseline_path(profile["name"])
    try:
        new = compliance.new_failures(kind, results, compliance.read_baseline(path), path)
    except compliance.BaselineMissing as e:
        pytest.fail(str(e))
    assert new == [], f"new v4l2-compliance failures ({kind}): {new}"


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="accepted v4l2-compliance failure (baseline)")
def test_known_failure(compliance_results, known_failure):
    kind, name = known_failure
    # a missing test raises LookupError: an error, not "fixed, remove the baseline line"
    assert compliance.known_failure_status(compliance_results[kind], name) != "FAIL"
