# Test results: l4t-r39.2.1 on Jetson AGX Orin

Hardware test on 2026-10-02: AGX Orin devkit, stock Jetpack 7.2.1, IMX900
directly on the FPA-4.A/AGX, connector J5, 4 lanes. The drivers, build,
install and test suite are the ones of the Orin Nano test in
[TEST-RESULTS-l4t-r39.2.1.md](TEST-RESULTS-l4t-r39.2.1.md).

## Summary

| Area | Result |
|---|---|
| Build on the Jetson (`target_build.sh check`) | ✅ 199 modules (24 `fr_*`), 192 overlays, about 3 min |
| Install (`install_all`): 42 modules into `updates/framos`, symbol CRCs against the stock modules | ✅ 0 problems; all 42 resolve to `updates/framos` |
| `jetson-config-camera(-cli).py` on the Jetpack 7 jetson-io | ✅ CLI and interactive tool write the same `FramosCamera` boot entry; `primary` unchanged |
| Probe, device tree, media graph | ✅ `imx900 9-001a` (J5 = FPA-4.A mux channel 0, bus 9) |
| Controls right after boot | ✅ 72 fps / 10 ms / gain 0 |
| Raw V4L2, 2064x1552 12/10/8-bit at maximum rate | ✅ 72.03 / 117.03 / 125.03 fps, no gaps, no CSI errors; also after a mode switch |
| Argus with `imx900_bottomleft_framos.nito` (finding 1) | ✅ mode 0 at 72.01 fps, mode 5 at 117.07 fps (VIC pinned at 729 MHz by the suite) |
| v4l2-compliance | ✅ the same 4 accepted NVIDIA failures as on the Orin Nano |
| `tests/hw` suite, fresh boot | ✅ 95 passed, 4 accepted compliance failures (commit fe6c39f) |

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

## Findings

### 1. The Orin Nano NITO does not work under the AGX badge

Argus looks for the NITO file whose embedded module name matches the module's
badge; the file name does not matter. The Nano's `imx900_rear_framos.nito`,
installed as `imx900_bottomleft_framos.nito`, is skipped ("No cameras
available", `NvCameraIspGetNitoPathIfEnabled() returned error`). With
`NVCAMERA_NITO_PATH` pointing at it, Argus loads it and streams mode 0 at
72 fps, so the tuning itself is fine. Editing the embedded name (offset 0xc0)
makes Argus reject the file as corrupt.

`isp/imx900_bottomleft_framos.nito` was therefore converted on the AGX with
NVIDIA's automatic conversion: camera hotfix installed, `IMX900_IRC650.isp`
as `camera_overrides.isp`, `NVCAMERA_NITO_PATH=CONFIG`, `nvargus_nvraw
--mode 0` and `--mode 5` (knob sets 0 and 5). The hotfix files were removed
afterwards (`dpkg -V nvidia-l4t-camera` clean); the test ran with the stock
camera libraries.

### 2. Open points from the bring-up, answered

- The FPA-4.A mux node merges with NVIDIA's disabled `tca9548@70` node; its
  channels are buses 9–16 and J5 is bus 9, as the overlay's `devname`
  expects.
- The mode 5 Argus rate needs the faster VIC clock as on the Orin Nano
  (finding 3 there); the AGX's VIC maximum is 729.6 MHz.

## 2048x1536 mode (2026-11-12)

The 2048x1536 ROI mode of framos-rpi-drivers (Sony's recommended recording
area, 8 px in from each edge) was added in 12, 10 and 8 bit. The DT modes are
now `mode0`-`mode5` 12-bit, `mode6`-`mode11` 10-bit and `mode12`-`mode17`
8-bit, each block ordered 2064x1552, 1920x1080, 1032x776, 2064x154, 1024x720,
2048x1536. 10-bit full resolution moved from mode 5 to mode 6; the results
above use the old numbers.

Same board and boot entry, fresh boot, `tests/hw` with the AGX profile
(results `agx-fpa4a-j5-direct-imx900-4lane-20261112-134026`): 104 passed,
4 accepted compliance failures, 1 failure (Argus mode 5, below), since
recorded as a known failure.

| Mode | Format | Maximum rate (control) | Measured |
|---|---|---|---|
| 2048x1536 12-bit (DT mode 5) | RG12 | 72.7 fps | 72.71 fps, no gaps |
| 2048x1536 10-bit (DT mode 11) | RG10 | 118.1 fps | 118.12 fps, no gaps |
| 2048x1536 8-bit (DT mode 17) | RGGB | 126.3 fps | 126.32 fps, no gaps |

- The 2064x1552 modes are unchanged: 72.03 / 117.03 / 125.03 fps.
- A new mode starts at its DT default rate (72 / 117 / 125 fps, the
  full-resolution values).
- A GBRG request at 2048x1536 is changed to RGGB with the driver's warning, as
  for 2064x1552.
- Argus: mode 0 at 72.0 fps and mode 6 (10-bit full resolution) at 117.08 fps
  with `imx900_bottomleft_framos.nito`. Mode 5 (2048x1536) gets no frames:
  `GetKnobSetIdFromSensorModeIndex: Sensor mode index 5, knobSetId 0 not
  found`. The NITO has knob sets only for the two modes it was converted with.
  Mode 1 (1920x1080), which predates this change, fails the same way. The
  regenerated NITO (next section) fixes both.

## NITO for the 2048x1536 and 1920x1080 modes (2026-11-12)

`isp/imx900_bottomleft_framos.nito` was regenerated with NVIDIA's Jetson
Customer IQ Migration Tools (r39.2.1, camera hotfix) on this board. Argus
with the new file, stock camera libraries (`tests/hw -m argus`):

| DT mode | Mode | Argus |
|---|---|---|
| 0 | 2064x1552 12-bit | 72.01 fps |
| 1 | 1920x1080 12-bit | 99.98 fps |
| 2 | 1032x776 12-bit | about 137 fps (DT maximum 250; not in the profile) |
| 5 | 2048x1536 12-bit | 71.97 fps |
| 6 | 2064x1552 10-bit | 116.99 fps |
| 7 | 1920x1080 10-bit | 160.55 fps |

Findings:

- **Argus looks up tuning for sensor modes 0-7 only.** Knob sets made from
  modes 8 and 11 (1032x776 and 2048x1536 10-bit) are in the file but Argus
  reports `GetKnobSetIdFromSensorModeIndex: Sensor mode index 11, knobSetId 0
  not found`. With the DT order of 12-bit, 10-bit, 8-bit blocks, 2048x1536
  10-bit and all 8-bit modes cannot be used in Argus.
- **Argus matches a knob set to a mode by size and bit depth, not by knob set
  ID**: mode 7 works from knob set 5.
- **Every NITO needs mode 0's knob set.** Argus initialises the ISP with mode
  0. A NITO without a 2064x1552 12-bit knob set fails in every mode
  (`NvCameraIspInitialize failed`).
- **`nvcfg2nito` aborts when its source NITO holds a knob set whose mode
  runs above about 250 fps.** The binary cfgs differ only in width, height, bit
  depth and the DT maximum frame rate (float at offset 148). Modes 3, 8, 9
  and 10 (377-632 fps) produce knob sets that can be written once but not read
  back as the source of the next conversion (`Aborted`, exit 134). The
  daemon's auto-conversion therefore also fails after such a mode.
- 2064x154 (modes 3, 9): Argus sessions hang (`waitForIdle() timed out`).
- 1024x720 (modes 4, 10): the driver changes 1024x720 to 2064x1552 on colour
  sensors (binning is for mono). Argus then gets full-size frames and fails
  with `Error 15`.

Procedure: the hotfix files from `camera_hotfix.tbz2` were copied in place
by hand (the installer works over SSH only), with the overwritten
`libnvscf.so` and NITOs backed up. `IMX900_IRC650.isp` was installed as
`/var/nvidia/nvcam/settings/camera_overrides.isp`, and `nvargus-daemon` was
run with `NVCAMERA_NITO_PATH=CONFIG`. One Argus session per mode, modes 0-11
(`nvarguscamerasrc sensor-mode=N`; `nvargus_nvraw` rejects the GBRG modes 2
and 3), wrote `/root/binary_N.cfg`. The NITO was then built by chaining
`nvcfg2nito` from the hotfix's `template.nito`: each run's output is the next
run's `-s`. Order: modes 0, 1, 2, 5, 6, 7 into knob sets 0, 1, 2, 5, 6, 7.
The badge name comes from the binary cfg. Afterwards the backups were put
back and the added files removed. `dpkg -V nvidia-l4t-camera` was clean.
The file is 958,476 bytes, like every NITO (the template's size), and about
22 KB compressed.

## Mode order for 2048x1536 10-bit in Argus (2026-11-12, evening)

2048x1536 10-bit was DT mode 11 and out of Argus' reach (modes 0-7 only). The
2048x1536 modes now follow full resolution in each bit-depth block: 2064x1552,
2048x1536, 1920x1080, 1032x776, 2064x154, 1024x720. The sections above use
the earlier numbers. The NITO was regenerated the same way, for modes 0, 1,
2, 3, 6, 7 (all at or below 250 fps, so no binary cfg needed patching).
`tests/hw` now also checks that each Argus sensor mode number selects the
expected resolution (nvarguscamerasrc lists the modes; its output follows
the caps, so the rate alone does not show the mode).

| Argus mode | Mode | Argus |
|---|---|---|
| 0 | 2064x1552 12-bit | 71.98 fps |
| 1 | 2048x1536 12-bit | 72.03 fps |
| 2 | 1920x1080 12-bit | 100.08 fps |
| 6 | 2064x1552 10-bit | 117.03 fps |
| 7 | 2048x1536 10-bit | 117.10 fps |

`tests/hw` without the after-boot controls check: 111 passed, 4 accepted
compliance failures.

## Not tested

- Connectors J6–J8, 1/2-lane configurations, more than one camera at a time.
- IMX900 modes other than the full-resolution and 2048x1536 ones, trigger and
  sync modes, mono sensors, image quality, long-term stability.
