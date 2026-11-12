import pytest

from lib.sysinfo import install_type, l4t_release

pytestmark = pytest.mark.unit


def test_l4t_release():
    assert l4t_release("# R39 (release), REVISION: 2.1, GCID: 46758480, BOARD: generic") == "39.2.1"
    assert l4t_release("# R36 (release), REVISION: 4.4, GCID: 41062509, BOARD: generic") == "36.4.4"
    assert l4t_release("garbage") == "unknown"


@pytest.mark.parametrize("ksyms,path,expected", [
    ("ffff0 T regmap_util_write_table_32\t[tegra_camera]",
     "/lib/modules/k/updates/framos/tegra-camera.ko", "framos-depmod"),
    ("ffff0 T regmap_util_write_table_32\t[tegra_camera]",
     "/lib/modules/k/updates/drivers/x/tegra-camera.ko", "framos-in-tree"),
    ("ffff0 T regmap_util_write_table\t[tegra_camera]",
     "/lib/modules/k/updates/drivers/x/tegra-camera.ko", "nvidia-stock"),
])
def test_install_type(ksyms, path, expected):
    assert install_type(ksyms, path) == expected
