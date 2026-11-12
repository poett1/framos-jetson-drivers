import pytest

from lib.kmsg import CSI_ERROR_RE, new_errors

pytestmark = pytest.mark.unit


def test_new_errors_only_after_mark():
    before = ["a", "tegra-capture-vi: corr_err: discarding frame 1"]
    after = before + ["b", "tegra-capture-vi: uncorr_err: request timed out after 2500 ms"]
    assert new_errors(before, after) == ["tegra-capture-vi: uncorr_err: request timed out after 2500 ms"]


def test_new_errors_after_ring_buffer_wrap():
    before = ["x1", "x2", "x3"]
    after = ["x3", "nvcsi 15a00000.nvcsi: PHY_INTR0 error"]
    assert new_errors(before, after) == ["nvcsi 15a00000.nvcsi: PHY_INTR0 error"]


def test_regex_ignores_normal_lines():
    assert not CSI_ERROR_RE.search("imx900 9-001a: Detected imx900 sensor")
