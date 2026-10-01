import subprocess
from pathlib import Path

BUILD = Path(__file__).resolve().parents[2] / "build"


def _bash(cmd):
    return subprocess.run(["bash", "-c", f"source {BUILD}/target_build.sh >/dev/null; {cmd}"],
                          capture_output=True, text=True, check=True).stdout


def test_override_lines_use_the_file_name():
    # kmod 31 (Ubuntu 24.04) matches depmod overrides against the file name:
    # "override tegra_camera" does not apply to tegra-camera.ko
    out = _bash("_override_lines /x/updates/drivers/tegra-camera.ko /y/fr_imx900.ko /z/nvhost-vi5.ko")
    assert out.splitlines() == ["override tegra-camera * updates/framos",
                                "override fr_imx900 * updates/framos",
                                "override nvhost-vi5 * updates/framos"]
