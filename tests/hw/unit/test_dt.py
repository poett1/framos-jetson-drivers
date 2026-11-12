import pytest

from lib.dt import active_badges, children, read_str, read_strlist

pytestmark = pytest.mark.unit


def _prop(root, path, value):
    p = root / path.lstrip("/")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(value)


@pytest.fixture
def tree(tmp_path):
    _prop(tmp_path, "/compatible", b"nvidia,p3737-0000+p3701-0005\0nvidia,p3701-0005\0")
    mods = "/tegra-camera-platform/modules"
    _prop(tmp_path, f"{mods}/module0/status", b"okay\0")
    _prop(tmp_path, f"{mods}/module0/badge", b"imx900_bottomleft_framos\0")
    _prop(tmp_path, f"{mods}/module1/status", b"disabled\0")
    _prop(tmp_path, f"{mods}/module1/badge", b"imx900_centerright_framos\0")
    _prop(tmp_path, f"{mods}/module2/badge", b"no_status_means_okay\0")
    return tmp_path


def test_read_strlist(tree):
    assert read_strlist("/compatible", tree) == ["nvidia,p3737-0000+p3701-0005", "nvidia,p3701-0005"]


def test_read_str_missing_is_none(tree):
    assert read_str("/nope", tree) is None
    assert read_strlist("/nope", tree) == []


def test_children(tree):
    assert children("/tegra-camera-platform/modules", tree) == ["module0", "module1", "module2"]
    assert children("/nope", tree) == []


def test_active_badges(tree):
    assert active_badges(tree) == ["imx900_bottomleft_framos", "no_status_means_okay"]
