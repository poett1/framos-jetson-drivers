# Test results: l4t-r39.2.1 on Jetson Orin Nano

Two hardware tests of this branch on an Orin Nano devkit Super:

- **2026-10-01, stock Jetpack 7.2.1**, built and installed on the Jetson with
  `build/target_build.sh`, IMX900 directly on FPA-A/P22 and over GMSL3, checked
  with the `tests/hw` suite against a Jetpack 6 reference (next section);
- **2026-09-28, Yocto image** (OE4T meta-tegra), IMX900 over GMSL3 (further
  below).

# Stock Jetpack 7.2.1, 2026-10-01

## Summary

| Area | Direct (FPA-A/P22 cam1) | GMSL3 (FPA-A/P22 cam1) |
|---|---|---|
| Build on the Jetson, install (42 modules into `updates/framos`) | ✅ 199 modules (24 `fr_*`), 192 overlays, 5 min 50 s | same install |
| Probe, device tree, media graph | ✅ | ✅ |
| Controls right after boot | ✅ 72 fps / 10 ms / gain 0 | ✅ same |
| Raw V4L2, 2064x1552 12/10/8-bit at maximum rate | ✅ 72.03 / 117.03 / 125.03 fps, no gaps, no CSI errors | ✅ same |
| Argus with `imx900_rear_framos.nito`, mode 0 (12-bit) | ✅ 72 fps | ✅ 72 fps |
| Argus mode 5 (10-bit, 117 fps) | ⚠ 58.5 fps at the default VIC clock, 117 fps with VIC at maximum or `jetson_clocks` (finding 3) | same |
| v4l2-compliance | ✅ 4 accepted NVIDIA failures (baseline) | ✅ same |
| `tests/hw` suite, fresh boot | ✅ all pass except Argus mode 5 (run before the suite pinned VIC) | ✅ 95 passed, 4 accepted compliance failures (2026-10-02, VIC pinned) |

## Setup

- **Board:** Orin Nano Engineering Reference Developer Kit Super (p3768 +
  p3767-0005).
- **Software:** stock Jetpack 7.2.1, L4T R39.2.1 (GCID 46758480), kernel
  `6.8.12-1021-tegra`, flashed with SDK Manager. This branch built and
  installed on the Jetson: `source build/target_build.sh; check; install_all`,
  then `tools/jetson-config-camera-cli.py`.
- **Camera:** color IMX900 on the FPA-A/P22, cam1, 4 lanes; directly
  (overlays `fr_fpa_a_p22`, `fr_imx900-cam1-4lane`) and over GMSL3 (MAX96793
  serializer at 0x42, MAX96792 deserializer at 0x6a, plus `fr_cam1-gmsl`).
- **NITO:** `isp/imx900_rear_framos.nito` installed as
  `/var/nvidia/nvcam/settings/imx900_rear_framos.nito`. Argus finds it by the
  badge and uses its knobsets 0 and 5 (sensor modes 0 and 5).
- **Tests:** `sudo python3 -m pytest tests/hw --profile=tests/hw/profiles/nano-p3768-cam1-{direct,gmsl}-imx900-4lane.yaml`
  on a freshly booted board; profiles and compliance baselines are in the
  repository.

## Jetpack 6 reference

The same board, sensor and suite on stock Jetpack 6.2.1 (L4T 36.4.4) with
FRAMOS' official l4t-r36.4.4 driver, installed per the FRAMOS wiki, Argus with
`IMX900_IRC650.isp` as `camera_overrides.isp`. Profiles
`nano-p3768-cam1-{gmsl,direct}-imx900-4lane-jp6`.

| Check | Jetpack 6 + l4t-r36.4.4 | Jetpack 7.2.1 + this branch |
|---|---|---|
| Probe, device tree, media graph | ✅ | ✅ |
| Controls right after boot | ❌ 1.5 fps / 9 µs (control minimum) | ✅ 72 fps / 10 ms (fixed in 3367073) |
| Raw V4L2 12/10/8-bit | 72.03 / 117.03 / 125.03 fps | 72.03 / 117.03 / 125.03 fps |
| Argus mode 0 / mode 5 | 72 / 58–72 fps (VIC not pinned) | 72 / 58.5 fps; 72 / 117 fps with VIC at maximum (finding 3) |
| v4l2-compliance | 3 accepted failures | the same 3 + 1 (finding 4) |

## Findings

### 1. The depmod override has to name the module file (fixed)

kmod 31 (Ubuntu 24.04) matches an `override` line against the module's file
name. `override tegra_camera` did not apply to `tegra-camera.ko`; the six stock
modules with a dash in their name then resolved to whichever `updates/`
subdirectory depmod read first: `updates/framos` on the AGX Orin, the stock
directory on the Orin Nano, where the install's own check stopped it.
`target_build.sh` writes the file names since 87b8734.

### 2. v4l2-compliance leaves the sensor in slave mode

`v4l2-compliance -u` sets the FRAMOS menu controls to test values and does not
restore them: `operation_mode` = Slave Mode, `data_rate` = 594 Mbps/lane,
`test_pattern` = color bars. In slave mode the IMX900 waits for external sync
and sends no frames. The suite restores all writable controls after
v4l2-compliance and runs it last. After standalone v4l2-compliance runs, a
reboot was needed before raw V4L2 streamed again (seen on Jetpack 6, with the
control values restored); run the suite on a freshly booted board.

### 3. Argus delivers mode 5 at half rate at the default VIC clock

In mode 5 (2064x1552, 10-bit) the sensor runs at 117 fps (VMAX 1743 at a line
time of 4.902 µs) and raw V4L2 receives 117 fps, but `nvarguscamerasrc`
delivers 58.5 fps, every second frame. It held on stock Jetpack 7.2.1 with both
connections, with the ISP at 729.6 MHz and EMC at 3.2 GHz (power mode
MAXN_SUPER), with a fixed exposure and gain, and on stock Jetpack 6.

The cause is the VIC clock, which converts each frame for `nvarguscamerasrc`.
Its devfreq governor (`tegra_wmark`, `/sys/class/devfreq/15340000.vic`)
settles too low for 2064x1552 at 117 fps. NVIDIA's libargus sample `yuvJpeg`
(no GStreamer, JPEG encoding left out) receives mode 5 at 117.03 fps with every
sensor frame at the default clocks. Each case below is the first Argus session
after a reboot, stock Jetpack 7.2.1, GMSL3:

| Clocks | Argus mode 5 | VIC during the capture |
|---|---|---|
| default | 58.5 fps for the whole run | 435 MHz for 3 s, then 166–192 MHz |
| VIC `min_freq` set to `max_freq` | 115.5–117.2 fps | 435 MHz |
| `sudo jetson_clocks` | 117.0 fps | 332–358 MHz (jetson_clocks does not set VIC; its governor goes higher with CPU, GPU and EMC at maximum) |

The `tests/hw` suite pins VIC at its maximum during each Argus test (fixture
`vic_max`, `tests/hw/lib/clocks.py`) and restores it afterwards. With that,
mode 5 passes at 117.04 fps (2026-10-02). For applications, `sudo jetson_clocks`
or pinning VIC alone works:

```
echo $(cat /sys/class/devfreq/15340000.vic/max_freq) | \
    sudo tee /sys/class/devfreq/15340000.vic/min_freq
```

The VIC clock of the Yocto image of 2026-09-28 was not measured; it delivered
mode 5 at 117 fps after a slow start that finding 8 addresses.

### 4. Compliance baseline: one more entry on Jetpack 7.2.1

The video node's "MC information" check fails on the nvcsi entity's function
`0x0002000a` ("Unknown sub-device"). Jetpack 6's v4l2-compliance 1.22 reports
the same value without failing; 1.26 fails it. The other three accepted
failures are the same on both releases: NVIDIA's media graph
(`MEDIA_IOC_ENUM_ENTITIES/LINKS`, `MEDIA_IOC_G_TOPOLOGY`) and the tegracam
subdev without control events.

### 5. After Argus, raw V4L2 needs `bypass_mode=0`

Argus leaves the sensor's `bypass_mode` at 1 (and `override_enable` at 1). A
raw V4L2 stream after an Argus session then gets no frames until
`v4l2-ctl -d /dev/video0 -c bypass_mode=0` is set; no reboot is needed. The
suite's Argus fixture resets it. (This was found on the Yocto image first.)

Stopping such a stream, or any stream that never received a frame (for example
in slave mode, finding 2), logs `videobuf2_common: driver bug: stop_streaming
operation is leaving buffer N in active state` and a WARNING in
`videobuf2-core.c:2102`. NVIDIA's VI driver (`vi5_fops.c`) returns the buffers
in its capture and dequeue lists, but not those its dequeue thread holds or
the RCE still has. FRAMOS does not change this code; the kernel reclaims the
buffers.

### 6. Failed Argus sessions leave per-frame errors behind

An Argus session that ends abnormally (for example when nvargus-daemon is
restarted while it streams, or a mode without a NITO knob set) leaves the
capture in a state where nearly every frame raises `SCF: Error 0x0000000f:
Error 15` (`CAPTURE_STATUS_CHANSEL_NOMATCH`, a frame without a matching capture
request). The stock `nvarguscamerasrc` treats these correctable events as
errors and stops after a few seconds. Restarting nvargus-daemon sometimes
clears it; a reboot always does. This explains the failures seen in the first
hour after flashing (mode 0 above its rate, mode 5 without frames); they did
not occur on freshly booted boards.

### 7. A marginal CSI cable loses stream starts

On the Jetpack 6 reference, one flex cable lost 7 of 20 stream starts per mode
(the VI discarded every frame of that start, `corr_err`, `err_data
0x02600062`); another cable of the same length passed 60 of 60. The first
cable works on a Raspberry Pi, which uses a lower lane rate; the IMX900 runs at
2376 Mbps/lane here.

### 8. A new mode started at the previous mode's frame rate (fixed)

`camera_common` selects the mode by size only, so the `frame_rate` control kept
the previous mode's value across a 12/10/8-bit switch, and tegracam's
stream-start override programmed VMAX from it. A raw V4L2 stream that sets no
rate ran at 72 fps in mode 5 and mode 10 after mode 0; Argus started mode 5 at
72 fps timing (VMAX `0xb11`) and got every second frame until it re-sent its
settings. Since a4b8bf5, `fr_imx900` sets a new mode's DT default frame rate
when the mode changes; a rate set within one mode is kept. Test
`test_mode_switch_starts_at_mode_default_rate`: before 72.07 / 72.08 / 72.07
fps, after 72.03 / 117.03 / 125.03 fps.

## Not tested (2026-10-01)

- Orin NX (profiles `nx-p3768-cam1-{direct,gmsl}-imx900-4lane` exist).
- AGX Orin with the FPA-4.A/AGX: built and installed, hardware test pending,
  see [TEST-RESULTS-l4t-r39.2.1-agx.md](TEST-RESULTS-l4t-r39.2.1-agx.md).
- IMX900 modes other than the three full-resolution ones, 1/2-lane
  configurations, trigger and sync modes, image quality, long-term stability.

# Yocto image, 2026-09-28

Hardware test of this branch, 2026-09-28.

## Summary

| Area | Result |
|---|---|
| Build, 24 driver modules and 192 overlays | ✅ builds against L4T 39.2.1, kernel 6.8.12 |
| IMX900 probe over GMSL3 | ✅ detected, bound to tegra-capture-vi |
| Raw V4L2 capture, 2064x1552 in 12/10/8-bit | ✅ 72 fps by default; each full-resolution mode reaches its maximum (72/117/125 fps), no CSI errors (issue 1, fixed) |
| Argus (nvarguscamerasrc, argus samples) | ❌ at first: Jetpack 7.2 needs a NITO tuning file (issue 2); ✅ later that day with the NITO generated on this image: mode 0 at 72 fps, mode 5 at 117 fps |

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

### 2. Argus needs a NITO file on Jetpack 7.2 (resolved)

Later on 2026-09-28 the NITO file was generated on this image with NVIDIA's
automatic conversion (camera hotfix, `NVCAMERA_NITO_PATH=CONFIG`,
`nvargus_nvraw --mode 0` and `--mode 5`), giving knob sets 0 and 5. With it,
Argus delivered mode 0 at 72 fps and mode 5 at 117 fps. The file is
`isp/imx900_rear_framos.nito`; for stock Jetpack 7.2.1 see the section above.

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
