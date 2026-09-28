# Test results: l4t-r39.2.1 on Jetson Orin Nano

Hardware test of this branch, 2026-09-28.

## Summary

| Area | Result |
|---|---|
| Build, 24 driver modules and 192 overlays | ✅ builds against L4T 39.2.1, kernel 6.8.12 |
| IMX900 probe over GMSL3 | ✅ detected, bound to tegra-capture-vi |
| Raw V4L2 capture, 2064x1552 in 12/10/8-bit | ✅ 72 fps by default; each full-resolution mode reaches its maximum (72/117/125 fps), no CSI errors (issue 1, fixed) |
| Argus (nvarguscamerasrc, argus samples) | ❌ no camera: Jetpack 7.2 needs a NITO tuning file, and there is none for the IMX900 (issue 2) |

## Setup

- **Board:** NVIDIA Jetson Orin Nano Engineering Reference Developer Kit Super
  (p3768 carrier, p3767-0005 module).
- **Software:** L4T R39.2.1 (GCID 46758480), kernel `6.8.12-l4t-r39.2.1-1021.21`.
  Built with Yocto (OE4T meta-tegra, wrynose branch, commit 2e37d167) from
  this branch's sources as one patch on the stock `nvidia-kernel-oot` 39.2.1
  sources.
- **Camera:** FRAMOS IMX900 over GMSL3. The serializer is a MAX96793 (I2C 0x42)
  and the deserializer a MAX96792 (I2C 0x6a), with the FPA-A/P22 adapter on
  the devkit's CAM1 connector. The CSI cable between deserializer and Jetson
  was longer than usual.
- **Overlays**, applied by the UEFI plugin manager:
  `tegra234-p3767-camera-p3768-fr_fpa_a_p22-overlay.dtbo`,
  `tegra234-p3767-camera-p3768-fr_imx900-cam1-4lane-overlay.dtbo`,
  `tegra234-p3767-camera-p3768-fr_cam1-gmsl-overlay.dtbo`.
- **ISP override file:** `isp/IMX900_IRC650.isp` installed as
  `/var/nvidia/nvcam/settings/camera_overrides.isp`.

## Checks and results

### Probe

`fr_imx900`, `fr_common`, `fr_max96792` and `fr_max96793` load. `dmesg`:

```
imx900 9-001a: probing v4l2 sensor
imx900 9-001a: initializing GMSL...
imx900 9-001a: tegracam sensor driver:imx900_v2.0.6
tegra-camrtc-capture-vi tegra-capture-vi: subdev imx900 9-001a bound
imx900 9-001a: Detected imx900 sensor
```

`/dev/video0` and `/dev/media0` exist. The media graph is
`imx900 9-001a` (SRGGB12_1X12 2064x1552) → `nvcsi` → `vi-output, imx900 9-001a`.

### Raw V4L2 capture

This command delivered all 400 frames:

```
gst-launch-1.0 v4l2src device=/dev/video0 num-buffers=400 \
    extra-controls="c,frame_rate=60000000" \
    ! "video/x-bayer,format=rggb12le,width=2064,height=1552" \
    ! fakesink sync=false
```

The frame interval was a steady 16.7 ms (60 fps). The kernel logged no CSI or
PHY errors, over the longer-than-usual CSI cable.

Without explicit caps, `v4l2src` negotiates `gbrg12le` at 1032x776. The driver
then logs `selected mode is not supported with GBRG12 pattern, switching to
RGGB12`.

### Full-resolution modes, 12/10/8-bit

The driver selects the mode from the requested pixel format at 2064x1552, and
the `Frame Rate` control range follows the mode. Each stream was started, then
`Frame Rate` was set to the mode's maximum while streaming. The table gives the
steady-state interval over the last 300 frames:

| Mode | Format (GStreamer caps) | Frame Rate set | Measured interval | Frame rate |
|---|---|---|---|---|
| mode 0 | 12-bit RGGB (`rggb12le`) | 72 fps | 13.9 ms | 72 fps |
| mode 5 | 10-bit RGGB (`rggb10le`) | 117 fps | 8.5 ms | ~117 fps |
| mode 10 | 8-bit RGGB (`rggb`) | 125 fps | 8.0 ms | 125 fps |

The control maxima reported per mode were 72.07, 117.04 and 125.18 fps. The
kernel logged no errors. Exposure was left at its (near-minimum) initial value,
so this checks timing, not image content.

### Argus

The ISP opens, but ISP initialisation fails for lack of a NITO file (issue 2).

## Known issues

### 1. V4L2 controls started at their minimum values (fixed)

**Fixed in 33670738** ("fr_imx900: start GAIN, EXPOSURE and FRAME_RATE at their
DT defaults"). Verified on 2026-09-28.

Before the fix, the current values after probe were `Frame Rate` = 1500000
(1.5 fps) and `Exposure` near its minimum, although the DT defaults are 72 fps
and 10 ms for mode 0. So a raw V4L2 capture that set no controls ran at 1.5 fps,
in every mode.

The cause is the ordering in the tegracam control init. The controls are
created with placeholder defaults, then their ranges are narrowed to the
mode's DT values. Narrowing clamps the current value to the new minimum
instead of loading the DT default. Argus sets these controls itself, which
hides the problem.

The driver now copies the DT defaults into the controls at probe. There is no
register access: `imx900_set_mode()` enables `override_enable`, so tegracam
applies the current values at every stream start.

After a fresh boot, `v4l2-ctl -C frame_rate -C exposure -C gain` gives
`72000000` / `10000` / `0`. A plain
`gst-launch-1.0 v4l2src ! "video/x-bayer,format=rggb12le,width=2064,height=1552" ! fakesink`
runs at 72 fps.

**Setting the frame rate.** `Frame Rate`, `Exposure` and `Gain` are 64-bit
controls. GStreamer's `v4l2src extra-controls` skips them ("Control type ...
not supported for extra controls"), and caps `framerate` is not passed to the
sensor. Use `VIDIOC_S_EXT_CTRLS`, for example
`v4l2-ctl -d /dev/video0 --set-ctrl frame_rate=117000000` (the value is fps ×
10^6).

The control range is the range of the mode that streamed last. It only
changes at stream start, not when the format is set:

- Rates inside the active mode's range can be set any time, before or during
  streaming, and are kept for later streams.
- Rates above the last mode's limit, such as 117 fps for the 10-bit mode after
  a 12-bit stream (limit 72 fps), are clamped when set before streaming. Set
  them while the stream in the target mode runs. After that the value is kept,
  and the next stream in that mode starts at it.

### 2. Argus needs a NITO file on Jetpack 7.2

Jetpack 7.2 uses NITO tuning files only. Argus logs:

- with the `.isp` override only: `NvCameraIspGetNitoPathIfEnabled() returned
  error`;
- with `NVCAMERA_NITO_PATH=CONFIG`, which was the Jetpack 7.0/7.1 fallback:
  "legacy way of using text based configuration file ... is not allowed
  anymore". In this mode Argus writes a binary config generated from
  `camera_overrides.isp` to `$HOME/binary.cfg`, and NVIDIA's Windows tuning
  tool converts that file to a NITO file.

The module's badge `imx900_rear_framos` is not one Argus knows ("Could not map
module to ISP config string").

A stand-in NITO from another sensor does not work either. With NVIDIA's
`imx477.nito`, Argus reports `knobSetId 0 not found`, because the knob sets are
tied to the IMX477's sensor modes.

**Argus capture on Jetpack 7.2 needs an IMX900 NITO file**, from FRAMOS or
converted from the binary config above.

### 3. `serdes_pix_clk_hz` of the GMSL modes

The GMSL overlays set `serdes_pix_clk_hz = "12000000000"`, the GMSL3 link
rate. The camera core uses that value to derive the CSI clock, so the RCE
firmware reports `MIPI clock rate: 18000000 kHz` and configures T_HS settle
automatically from it. Capture was clean in this test anyway. If CSI errors
appear with other cables or modes, correcting this value, or setting
`cil_settletime`, is a place to start.

## Not tested

- Sensors other than the IMX900. IMX900 modes below full resolution; the
  binned 1032x776 mode only ran at the 1.5 fps default (issue 1).
- The direct MIPI (non-GMSL) connection.
- AGX Orin (p3737).
- Trigger and sync modes.
- Image quality.
- Long-term stability.
