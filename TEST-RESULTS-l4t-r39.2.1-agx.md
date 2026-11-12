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
  Mode 1 (1920x1080), which predates this change, fails the same way. Argus at
  2048x1536 needs a NITO converted with that mode as well.

## Not tested

- Connectors J6–J8, 1/2-lane configurations, more than one camera at a time.
- IMX900 modes other than the full-resolution and 2048x1536 ones, trigger and
  sync modes, mono sensors, image quality, long-term stability.
