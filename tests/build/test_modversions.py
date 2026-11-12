import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "build"))

from modversions import (  # noqa: E402
    check_imports,
    check_reverse_deps,
    parse_symvers,
    parse_versions,
)


def _entry(crc, name):
    raw = name.encode() + b"\0"
    raw += b"\0" * (-len(raw) % 4)
    return struct.pack("<II", 8 + len(raw), crc) + raw


def test_parse_versions_variable_length():
    blob = _entry(0x12C55898, "vb2_queue_init") + _entry(0x1, "module_layout")
    assert parse_versions(blob) == {"vb2_queue_init": 0x12C55898, "module_layout": 0x1}


def test_parse_symvers(tmp_path):
    p = tmp_path / "Module.symvers"
    p.write_text("0x33d9ba9b\tnvcsi_cil_sw_reset\t/x/drivers/video/tegra/host/nvcsi/nvhost-nvcsi"
                 "\tEXPORT_SYMBOL_GPL\t\n0xf7370f56\tsystem_state\tvmlinux\tEXPORT_SYMBOL\n")
    assert parse_symvers(p) == {"nvcsi_cil_sw_reset": (0x33D9BA9B, "nvhost_nvcsi"),
                                "system_state": (0xF7370F56, "vmlinux")}


def test_import_from_stock_module_with_other_crc_is_reported():
    imports = {"tegra_camera": {"host1x_fence_get": 0xAAAA, "camera_common_s_fmt": 0x1}}
    ours = {"host1x_fence_get": (0xAAAA, "host1x"), "camera_common_s_fmt": (0x1, "tegra_camera")}
    stock = {"host1x_fence_get": (0xBBBB, "host1x")}
    problems = check_imports(imports, {"tegra_camera"}, ours, stock)
    assert problems == ["tegra_camera: host1x_fence_get has CRC 0x0000aaaa, "
                        "stock host1x exports 0x0000bbbb"]


def test_import_inside_installed_set_is_fine():
    imports = {"fr_imx900": {"camera_common_s_fmt": 0x1}}
    ours = {"camera_common_s_fmt": (0x1, "tegra_camera")}
    stock = {"camera_common_s_fmt": (0x2, "tegra_camera")}
    assert check_imports(imports, {"fr_imx900", "tegra_camera"}, ours, stock) == []


def test_import_nobody_exports_is_reported():
    problems = check_imports({"fr_imx900": {"nowhere": 0x5}}, {"fr_imx900"}, {}, {})
    assert problems == ["fr_imx900: nowhere is exported by no module"]


def test_stock_module_depending_on_replaced_module_is_reported():
    deps = {"nvgpu": ["host1x"], "some_stock": ["tegra_camera", "videodev"]}
    assert check_reverse_deps(deps, {"tegra_camera", "fr_imx900"}) == [
        "stock some_stock depends on replaced tegra_camera"]


def test_import_from_our_module_that_is_not_installed_nor_stock_is_reported():
    # fr_x imports from our hwpm build, which _camera_stack leaves out and stock does not
    # ship: modprobe fr_x would fail with "Unknown symbol"
    imports = {"fr_x": {"tegra_hwpm_x": 0x5}}
    ours = {"tegra_hwpm_x": (0x5, "nvhwpm")}
    problems = check_imports(imports, installed={"fr_x"}, ours=ours, stock={})
    assert problems == ["fr_x: tegra_hwpm_x comes from nvhwpm, which is neither installed nor stock"]
