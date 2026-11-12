import subprocess

import pytest
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


KO = sorted((BUILD.parent / "source" / "nvidia-oot").rglob("fr_imx900.ko"))


def _bash_rc(cmd, env=None):
    import os
    r = subprocess.run(["bash", "-c", f"source {BUILD}/target_build.sh >/dev/null; {cmd}"],
                       capture_output=True, text=True, env={**os.environ, **(env or {})})
    return r.returncode, r.stdout + r.stderr


@pytest.mark.skipif(not KO, reason="needs a built tree (target_build.sh check)")
def test_vermagic_must_match_the_kernel():
    rc, out = _bash_rc(f"_check_vermagic {KO[0]}")
    assert rc == 0, out
    rc, out = _bash_rc(f"KERNEL_RELEASE=0.0.0-other _check_vermagic {KO[0]}")
    assert rc == 1 and "0.0.0-other" in out and "check" in out


def test_build_stamp_detects_changed_headers(tmp_path):
    symvers = tmp_path / "Module.symvers"
    symvers.write_text("0x1\tfoo\tvmlinux\tEXPORT_SYMBOL\n")
    env = {"STOCK_SYMVERS": str(symvers), "BUILD_STAMP": str(tmp_path / "stamp")}
    rc, out = _bash_rc("_check_build_stamp", env)
    assert rc == 1 and "check" in out                     # no stamp: never built here
    rc, out = _bash_rc("_write_build_stamp && _check_build_stamp", env)
    assert rc == 0, out
    symvers.write_text("0x2\tfoo\tvmlinux\tEXPORT_SYMBOL\n")  # headers package updated
    rc, out = _bash_rc("_check_build_stamp", env)
    assert rc == 1 and "other kernel headers" in out


def test_failed_install_rolls_back(tmp_path):
    # fake sudo/depmod; the verify step fails (modinfo -k does not know the fake tree)
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "sudo").write_text('#!/bin/sh\nexec "$@"\n')
    (fake / "depmod").write_text("#!/bin/sh\nexit 0\n")
    for f in fake.iterdir():
        f.chmod(0o755)
    mods = tmp_path / "modules"
    ko = tmp_path / "fr_imx900.ko"
    ko.write_bytes(b"not really a module")
    env = {"PATH": f"{fake}:/usr/bin:/bin", "MODULES_DIR": str(mods),
           "FRAMOS_MODULES_DIR": str(mods / "updates/framos"),
           "FRAMOS_DEPMOD_CONF": str(tmp_path / "framos.conf")}
    rc, out = _bash_rc(f"_install_files {ko}", env)
    assert rc == 1
    assert not (mods / "updates/framos").exists()
    assert not (tmp_path / "framos.conf").exists()
    assert "stock modules" in out and "rolled back" in out


def test_install_passes_only_existing_stock_symvers():
    # an unquoted /usr/src/nvidia/*/Module.symvers reaches modversions.py as the literal
    # pattern when nvidia-l4t-kernel-oot-headers is missing (FileNotFoundError)
    body = _bash("declare -f install_oot_modules")
    assert "/usr/src/nvidia/*" not in body
    assert "--stock-symvers ${STOCK_SYMVERS}" in body


@pytest.mark.skipif(not KO, reason="needs a built tree (target_build.sh check)")
def test_camera_stack_leaks_no_variables():
    # target_build.sh is sourced into the user's shell
    rc, out = _bash_rc("_camera_stack > /dev/null; declare -p dep ko name 2>&1")
    assert rc != 0 and "dep=" not in out and "ko=" not in out and "name=" not in out, out
