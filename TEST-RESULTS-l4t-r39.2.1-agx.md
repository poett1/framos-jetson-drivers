# Test results: l4t-r39.2.1 on Jetson AGX Orin

Status 2026-10-01: built, installed and configured on an AGX Orin devkit with
stock Jetpack 7.2.1. **The hardware test with the IMX900 on the FPA-4.A/AGX
is pending** (the adapter was not available). The Orin Nano results in
[TEST-RESULTS-l4t-r39.2.1.md](TEST-RESULTS-l4t-r39.2.1.md) cover the same
drivers, build, install and test suite.

## Summary

| Area | Result |
|---|---|
| Build on the Jetson (`target_build.sh check`) | ✅ 199 modules (24 `fr_*`), 192 overlays, about 3 min |
| Install (`install_all`): 42 modules into `updates/framos`, symbol CRCs against the stock modules | ✅ 0 problems; all 42 resolve to `updates/framos` |
| `jetson-config-camera(-cli).py` on the Jetpack 7 jetson-io | ✅ CLI and interactive tool write the same `FramosCamera` boot entry; `primary` unchanged |
| IMX900 on FPA-4.A/AGX J5, 4 lanes | ⏳ pending |

## Setup

- **Board:** AGX Orin Developer Kit, module p3701-0005 (64 GB), carrier p3737.
- **Software:** stock Jetpack 7.2.1, L4T R39.2.1 (GCID 46758480), kernel
  `6.8.12-1021-tegra`.
- **Boot entry** written by
  `tools/jetson-config-camera-cli.py -n "Framos FPA-4.A/AGX" "Framos IMX900-J5-4Lane"`:

  ```
  LABEL FramosCamera
  	FDT /boot/dtb/kernel_tegra234-p3737-0000+p3701-0005-nv.dtb
  	OVERLAYS /boot/framos/dtbo/tegra234-p3737-camera-fr_fpa_4a_agx-overlay.dtbo,/boot/framos/dtbo/tegra234-p3737-camera-fr_imx900-j5-4lane-overlay.dtbo
  ```

## To do with the FPA-4.A/AGX

1. Connect the IMX900 to J5 and boot the `FramosCamera` entry.
2. Check the probe: `imx900 9-001a` (the overlay expects the FPA-4.A mux
   channels on buses 9–16, J5 = bus 9).
3. Install the NITO under the AGX badge:
   `sudo install -m 644 isp/imx900_rear_framos.nito /var/nvidia/nvcam/settings/imx900_bottomleft_framos.nito`
   (if Argus rejects it, convert on the device with NVIDIA's camera hotfix).
4. On a freshly booted board:
   `sudo python3 -m pytest tests/hw --profile=tests/hw/profiles/agx-fpa4a-j5-direct-imx900-4lane.yaml -m compliance --write-compliance-baseline`,
   review the baseline (the Orin Nano baselines list the expected NVIDIA
   entries), reboot, then the full run without `--write-compliance-baseline`.

Open points the run answers: the I2C bus number of J5 (`devname`), the merge
of the FPA-4.A mux node with NVIDIA's disabled `tca9548@70` node, and whether
the Nano's NITO works under the AGX badge.
