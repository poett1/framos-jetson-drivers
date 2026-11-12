import pytest

from lib.clocks import find_vic, pin_max, restore_min

pytestmark = pytest.mark.unit


def _devfreq(root, name, cur=115200000, lo=115200000, hi=435200000):
    d = root / name
    d.mkdir(parents=True)
    for f, v in (("cur_freq", cur), ("min_freq", lo), ("max_freq", hi)):
        (d / f).write_text(f"{v}\n")
    return d


def test_find_vic(tmp_path):
    _devfreq(tmp_path, "17000000.gpu")
    vic = _devfreq(tmp_path, "15340000.vic")
    assert find_vic(tmp_path) == vic


def test_find_vic_none(tmp_path):
    _devfreq(tmp_path, "17000000.gpu")
    assert find_vic(tmp_path) is None
    assert find_vic(tmp_path / "missing") is None


def test_pin_max_and_restore(tmp_path):
    vic = _devfreq(tmp_path, "15340000.vic")
    before = pin_max(vic)
    assert before == 115200000
    assert (vic / "min_freq").read_text().strip() == "435200000"
    restore_min(vic, before)
    assert (vic / "min_freq").read_text().strip() == "115200000"
