import sys
from pathlib import Path

import pytest

JETSON_IO = Path("/opt/nvidia/jetson-io")
if not JETSON_IO.is_dir():
    pytest.skip("jetson-io not installed", allow_module_level=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(1, str(JETSON_IO))

from framos_jetsonio import header_defs, write_boot_entry  # noqa: E402

STOCK = """TIMEOUT 30
DEFAULT primary

MENU TITLE L4T boot options

LABEL primary
      MENU LABEL primary kernel
      LINUX /boot/Image
      INITRD /boot/initrd
      APPEND ${cbootargs} root=PARTUUID=x rw
"""


def test_boot_entry_added_and_default(tmp_path):
    f = tmp_path / "extlinux.conf"
    f.write_text(STOCK)
    write_boot_entry(str(f), "/boot/dtb/k.dtb", ["a.dtbo", "b.dtbo"], "FRAMOS camera")
    s = f.read_text()
    assert "DEFAULT FramosCamera" in s
    assert "LABEL primary" in s and "MENU LABEL primary kernel" in s
    assert "FDT /boot/dtb/k.dtb" in s
    assert "OVERLAYS /boot/framos/dtbo/a.dtbo,/boot/framos/dtbo/b.dtbo" in s
    assert "APPEND ${cbootargs} root=PARTUUID=x rw" in s.split("LABEL FramosCamera")[1]


def test_boot_entry_rewrite_keeps_one_label(tmp_path):
    f = tmp_path / "extlinux.conf"
    f.write_text(STOCK)
    write_boot_entry(str(f), "/boot/dtb/k.dtb", ["a.dtbo"], "x")
    write_boot_entry(str(f), "/boot/dtb/k.dtb", ["c.dtbo"], "x")
    s = f.read_text()
    assert s.count("LABEL FramosCamera") == 1
    assert "c.dtbo" in s and "a.dtbo" not in s


def test_24pin_alias_present():
    names = [h.name for h in header_defs()]
    assert "Jetson 24pin CSI Connector" in names
    assert "Jetson AGX CSI Connector" in names


def test_remove_boot_entry_restores_stock(tmp_path):
    from framos_jetsonio import remove_boot_entry
    f = tmp_path / "extlinux.conf"
    f.write_text(STOCK + "\n# When testing a custom kernel, ...\n")
    write_boot_entry(str(f), "/boot/dtb/k.dtb", ["a.dtbo"], "FRAMOS camera")
    remove_boot_entry(str(f))
    s = f.read_text()
    assert "FramosCamera" not in s and "a.dtbo" not in s
    assert "DEFAULT primary" in s
    assert "MENU LABEL primary kernel" in s and "APPEND ${cbootargs} root=PARTUUID=x rw" in s
    assert "# When testing a custom kernel" in s


def test_remove_boot_entry_without_entry_changes_nothing(tmp_path):
    from framos_jetsonio import remove_boot_entry
    f = tmp_path / "extlinux.conf"
    f.write_text(STOCK)
    remove_boot_entry(str(f))
    assert f.read_text() == STOCK


# "primary" as jetson-config-camera v2.0.0 left it: FDT and OVERLAYS added with sed
OLD_TOOL = STOCK.replace(
    "      APPEND ${cbootargs} root=PARTUUID=x rw\n",
    "      APPEND ${cbootargs} root=PARTUUID=x rw\n"
    "      FDT /boot/dtb/k.dtb\n"
    "      OVERLAYS /boot/framos/dtbo/old_a.dtbo,/boot/framos/dtbo/old_b.dtbo\n")


def test_remove_boot_entry_strips_old_tool_overlays_from_primary(tmp_path):
    # uninstall deletes /boot/framos/dtbo; primary must not point into it afterwards
    from framos_jetsonio import remove_boot_entry
    f = tmp_path / "extlinux.conf"
    f.write_text(OLD_TOOL)
    remove_boot_entry(str(f))
    s = f.read_text()
    assert "/boot/framos/dtbo" not in s and "OVERLAYS" not in s
    assert "FDT /boot/dtb/k.dtb" in s and "MENU LABEL primary kernel" in s


def test_remove_boot_entry_keeps_other_overlays(tmp_path):
    from framos_jetsonio import remove_boot_entry
    f = tmp_path / "extlinux.conf"
    f.write_text(OLD_TOOL.replace("/boot/framos/dtbo/old_b.dtbo", "/boot/other.dtbo"))
    remove_boot_entry(str(f))
    assert "      OVERLAYS /boot/other.dtbo\n" in f.read_text()


def test_boot_entry_leaves_primary_as_stock_fallback(tmp_path):
    f = tmp_path / "extlinux.conf"
    f.write_text(OLD_TOOL)
    write_boot_entry(str(f), "/boot/dtb/k.dtb", ["a.dtbo"], "FRAMOS camera")
    primary = f.read_text().split("LABEL FramosCamera")[0]
    assert "/boot/framos/dtbo" not in primary
    assert "OVERLAYS /boot/framos/dtbo/a.dtbo" in f.read_text()
