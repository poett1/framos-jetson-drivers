#!/usr/bin/env python3

import argparse
import sys
import importlib
import re
import os

sys.path.insert(1, "/opt/nvidia/jetson-io")
from Utils import dtc
from framos_jetsonio import FramosBoard, write_boot_entry
config_by_hardware = importlib.import_module("config-by-hardware")

extlinux_cfg = "/boot/extlinux/extlinux.conf"
dtbo_default_path = "/boot/framos/dtbo/"


def dtbo_file_exists(file):
    return os.path.exists(dtbo_default_path + file)

def main():
    parser = argparse.ArgumentParser(None, None, "Jetson Config Camera v2.1.0")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-n", "--name", nargs='*', help="\"<csi-module>\" ...")
    group.add_argument("-l", "--list", help="List of CSI modules", action='store_true')
    args = parser.parse_args()
    board_dtbo_template = ""
    selected_fpa = ""
    fpa_dtbo = ""

    jetson = FramosBoard()
    jetson.get_board_headers()
    if "Jetson AGX CSI Connector" in jetson.board_headers:
        header = "Jetson AGX CSI Connector"
        board_dtbo_template = "tegra234-p3737-camera-fr_" 
    elif "Jetson 24pin CSI Connector" in jetson.board_headers:
        header = "Jetson 24pin CSI Connector"
        board_dtbo_template = "tegra234-p3767-camera-p3768-fr_"
    else:
        print("Unknown board or no overlays found!")
        sys.exit(1)

    dtbos = []

    if args.list:
        config_by_hardware.show_hardware(jetson, header)

    fpa_selected = False
    if args.name:
        for arg in args.name:
            if not fpa_selected:
                match = re.match(r"^Framos ([FPAfpa]+)\-([0-9a-zA-z\/\.]+)$", arg)
                if match:
                    selected_fpa = match.group(2).lower()
                    fpa_selected = True
                    fpa_dtbo = board_dtbo_template + "fpa_" + selected_fpa + "-overlay.dtbo"
                    fpa_dtbo = fpa_dtbo.replace('/', '_')
                    if (fpa_dtbo.count('.') == 2):
                        fpa_dtbo = fpa_dtbo.replace('.', '', 1)

            match = re.match(r"^Framos ([a-zA-Z0-9_]+)\-([0-9a-zA-Z]+)\-([0-9a-zA-z]+)([-a-zA-Z]*)", arg)
            if (match):
                sensor = match.group(1).lower()
                port = match.group(2).lower()
                lanes = match.group(3).lower()
                gmslSelected = match.group(4).replace('-', '').lower()

                dtbo = board_dtbo_template + sensor + "-" + port + "-" + lanes + "-overlay.dtbo"
                dtbos.append(dtbo)

                if gmslSelected:
                    gmslDtbo = board_dtbo_template + port + "-gmsl-overlay.dtbo"
                    dtbos.append(gmslDtbo)

        if not selected_fpa:
            print("FPA overlay not specified. The script cannot continue.")
            sys.exit(1)
        dtbos.insert(0, fpa_dtbo)

        for dtbo in dtbos:
            if not dtbo_file_exists(dtbo):
                print(f"{dtbo} not found in {dtbo_default_path}.")
                print("This script cannot continue.")
                sys.exit(1)

        names = [dtc.get_prop_value(dtbo_default_path + dtbo, '/', 'overlay-name', 0) or dtbo
                 for dtbo in dtbos]
        write_boot_entry(extlinux_cfg, jetson.dtb, dtbos, "FRAMOS: " + ", ".join(names))

        print(f"{extlinux_cfg} updated.")
        print("Reboot the System to apply changes.")

if __name__ == '__main__':
    try:        
        main()
    except Exception as error:
        print(error)
