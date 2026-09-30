#!/usr/bin/env python3
#
# Shared jetson-io glue for jetson-config-camera.py and jetson-config-camera-cli.py
# on Jetpack 7:
#  - FramosBoard: jetson-io Board that loads the FRAMOS overlays from DTBO_DIR
#  - header_defs(): jetson-io header definitions plus "Jetson 24pin CSI Connector",
#    the header name of the p3767 FRAMOS overlays, which Jetpack 7 no longer defines
#  - write_boot_entry(): separate FramosCamera extlinux entry, the stock "primary"
#    entry stays as fallback

import copy
import os
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
    sig = extlinux_path + ".sig"
    if os.path.exists(sig):
        os.rename(sig, sig + ".jetson-io-backup")
