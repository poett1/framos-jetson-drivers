#!/usr/bin/env python3
#
# Shared jetson-io glue for jetson-config-camera.py and jetson-config-camera-cli.py
# on Jetpack 7:
#  - FramosBoard: jetson-io Board that loads the FRAMOS overlays from DTBO_DIR
#  - header_defs(): jetson-io header definitions plus "Jetson 24pin CSI Connector",
#    the header name of the p3767 FRAMOS overlays, which Jetpack 7 no longer defines
#  - write_boot_entry(): separate FramosCamera extlinux entry, the stock "primary"
#    entry stays as fallback; remove_boot_entry() takes it out again
#
# Command line: framos_jetsonio.py remove-boot-entry [extlinux.conf]

import copy
import os
import re
import sys

sys.path.insert(1, "/opt/nvidia/jetson-io")
from Jetson import board  # noqa: E402
from Linux import extlinux  # noqa: E402
from Utils import dtc  # noqa: E402
import Headers  # noqa: E402

DTBO_DIR = "/boot/framos/dtbo"
BOOT_LABEL = "FramosCamera"
HEADER_24PIN = "Jetson 24pin CSI Connector"
HEADER_22PIN = "Jetson 22pin CSI Connector"


def header_defs():
    """Return jetson-io's header definitions, with HEADER_24PIN added once."""
    names = [h.name for h in Headers.HDRS]
    if HEADER_24PIN not in names:
        alias = copy.copy(next(h for h in Headers.HDRS if h.name == HEADER_22PIN))
        alias.name = HEADER_24PIN
        Headers.HDRS.append(alias)
    return Headers.HDRS


class FramosBoard(board.Board):
    def __init__(self):
        super().__init__()
        dtbos = dtc.find_compatible_dtbo_files(self.compat.split(), DTBO_DIR)
        self.board_headers = board._board_load_headers(header_defs(), dtbos)


def write_boot_entry(extlinux_path, dtb, dtbos, menu_label):
    """Add or replace the FramosCamera entry and make it the default."""
    overlays = ",".join(f"{DTBO_DIR}/{d}" for d in dtbos)
    extlinux.add_entry(extlinux_path, BOOT_LABEL, menu_label, dtb, overlays, True)
    _strip_framos_overlays(extlinux_path)
    sig = extlinux_path + ".sig"
    if os.path.exists(sig):
        os.rename(sig, sig + ".jetson-io-backup")


# keywords of an extlinux entry's body, as in jetson-io's Linux/extlinux.py
_ENTRY_KEYWORDS = ("APPEND", "FDT", "FDTDIR", "INITRD", "LINUX", "MENU", "OVERLAYS")


def _strip_framos_overlays(extlinux_path):
    """Drop the DTBO_DIR overlays from every entry but FramosCamera, and an OVERLAYS line
    left empty. jetson-config-camera v2.0.0 put them into "primary" with sed; without
    this, "primary" is no stock fallback and points into DTBO_DIR after uninstall."""
    with open(extlinux_path) as f:
        lines = f.readlines()
    out, label = [], None
    for line in lines:
        words = line.split()
        if words[:1] == ["LABEL"]:
            label = words[1] if len(words) > 1 else ""
        elif words[:1] == ["OVERLAYS"] and label != BOOT_LABEL:
            overlays = [o for o in "".join(words[1:]).split(",") if o]
            keep = [o for o in overlays if not o.startswith(DTBO_DIR + "/")]
            if keep != overlays:
                if not keep:
                    continue
                indent = line[:len(line) - len(line.lstrip())]
                line = f"{indent}OVERLAYS {','.join(keep)}\n"
        out.append(line)
    if out != lines:
        with open(extlinux_path, "w") as f:
            f.writelines(out)


def remove_boot_entry(extlinux_path):
    """Remove the FramosCamera entry; if it was the default, make "primary" (or the first
    remaining entry) the default again. Also drops DTBO_DIR overlays left in other
    entries by the old tool. No change if there is neither."""
    _remove_entry(extlinux_path)
    _strip_framos_overlays(extlinux_path)


def _remove_entry(extlinux_path):
    with open(extlinux_path) as f:
        lines = f.readlines()
    out, labels, skipping = [], [], False
    for line in lines:
        words = line.split()
        if words[:1] == ["LABEL"]:
            skipping = len(words) > 1 and words[1] == BOOT_LABEL
            if not skipping:
                labels.append(words[1] if len(words) > 1 else "")
        elif skipping and (not words or words[0] in _ENTRY_KEYWORDS):
            continue
        else:
            skipping = False
        if not skipping:
            out.append(line)
    if len(out) == len(lines):
        return
    default = "primary" if "primary" in labels else (labels[0] if labels else None)
    if default:
        out = [re.sub(r"^DEFAULT\s+%s\s*$" % BOOT_LABEL, "DEFAULT %s" % default, l)
               if l.startswith("DEFAULT") else l for l in out]
        out = [l if not l.startswith("DEFAULT") or l.endswith("\n") else l + "\n" for l in out]
    while out and not out[-1].strip():
        out.pop()
    with open(extlinux_path, "w") as f:
        f.writelines(out)
        if out and not out[-1].endswith("\n"):
            f.write("\n")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "remove-boot-entry":
        remove_boot_entry(sys.argv[2] if len(sys.argv) > 2 else "/boot/extlinux/extlinux.conf")
    else:
        sys.exit("usage: framos_jetsonio.py remove-boot-entry [extlinux.conf]")
