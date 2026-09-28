&nbsp;
[Release Notes l4t‐r36.4.4](https://github.com/framosimaging/framos-jetson-drivers/wiki/Release-Notes-l4t%E2%80%90r36.4.4)

# Jetpack 7.2.1 / L4T 39.2.1 (branch l4t-r39.2.1)

This branch is a community port of the FRAMOS drivers to **Jetpack 7.2.1 /
L4T 39.2.1 (Nvidia tag `jetson_39.2.1`, kernel 6.8) for Jetson Orin**. It is
not an official FRAMOS release; FRAMOS' own Jetpack 7 branch (l4t-r38.4)
supports AGX Thor only.

- `source/` holds the clean L4T 39.2.1 kernel OOT sources (first commit),
  followed by the FRAMOS changes:
  - the camera-core changes (camera_common, sensor_common, tegracam_ctrls/v4l2,
    regmap_util, vi/channel.c, vi/vi5_fops.c and headers), taken from the
    l4t-r38.4 versions and fitted to 39.2.1;
  - the 50 fr_* sensor, serdes and bridge drivers, as in l4t-r36.4.4;
  - the 192 Orin overlays (p3767/p3768 Orin Nano/NX devkit, p3737 AGX Orin),
    as in l4t-r36.4.4.
- Build-tested on 2026-09-25 with OE4T meta-tegra (L4T 39.2.1, kernel
  6.8.12): all 24 driver modules and 192 overlays build.
- Hardware-tested on 2026-09-28 on an Orin Nano devkit Super with an IMX900
  over GMSL3 (fr_fpa_a_p22 + fr_imx900-cam1-4lane + fr_cam1-gmsl). The sensor
  probes, and raw V4L2 capture of 2064x1552 RGGB12 runs at 60 fps. **Argus does
  not work yet:** Jetpack 7.2 requires a NITO tuning file for the IMX900, and
  raw V4L2 capture must set `frame_rate`/`exposure` explicitly. See
  [TEST-RESULTS-l4t-r39.2.1.md](TEST-RESULTS-l4t-r39.2.1.md).
- `isp/`, `tools/`, `firmware/` and `build/` are carried unchanged from
  l4t-r36.4.4. The ISP override files are the Jetpack 6 ones (there are no
  .nito files for Jetpack 7), and the target/cross-compile scripts have not
  been adapted to 39.2.1. The procedure below still describes Jetpack 6.


# Short procedure

This list describes which Jetpack/L4T "Nvidia tag" and "Framos branch" to use for the desired Jetpack/L4T release.

If using target build, the "Framos branch" is used to checkout to compatible Framos drivers source code for the desired Jetpack/L4T.

If using cross-compilation, the "Nvidia tag" is used to checkout to correct tag of the Jetpack/L4T kernel source code and the "Framos branch" to checkout to compatible Framos drivers source code.

| Jetpack / L4T version |    Nvidia tag   |         Framos branch        |
|-----------------------|-----------------|------------------------------|
| ** 7.2.1 / 39.2.1     | jetson_39.2.1   | l4t-r39.2.1                  |
| 6.2.1 / 36.4.4        | jetson_36.4.4   | l4t-r36.4.4                  |
| * 6.2 / 36.4.3        | jetson_36.4.3   | l4t-r36.4.3                  |
| 6.1 / 36.4            | jetson_36.4     | l4t-r36.4                    |
| 6.0 / 36.3            | jetson_36.3     | l4t-r36.3                    |

_*_ [_Download overlay that fixes issue that causes blurry image capture (only Jetpack 6.2)_](https://developer.nvidia.com/embedded/jetson-linux-r3643#:~:text=Additional%20Files,for%20JetPack%206.2.1.)

_**_ _Community port for Jetson Orin; V4L2 capture tested, Argus needs an IMX900 NITO file. See the section at the top._

## 1. Get & Install Framos drivers
Two methods:
* [Using Framos source code on target system(Jetson platform)](https://github.com/framosimaging/framos-jetson-drivers/wiki/Clone,-Compile-and-Install-on-target-system(Jetson-platform))

  or

* [Using Framos source code on host system(Ubuntu 22.04)](https://github.com/framosimaging/framos-jetson-drivers/wiki/Clone,-Cross%E2%80%90Compile,-Install-and-flash-on-host-system(Ubuntu-22.04))

## 2. Configuration of Image Sensors on the Jetson platform (Target System)
Two methods:

* [Interactive version](https://github.com/framosimaging/framos-jetson-drivers/wiki/Interactive-version)

  or

* [Command line version](https://github.com/framosimaging/framos-jetson-drivers/wiki/Command-line-version)

## 3. Run streaming software
- **Optional:** [Apply the ISP override file](https://github.com/framosimaging/framos-jetson-drivers/wiki/FRAMOS-Sensor-Module-Ecosystem-%E2%80%90-ISP-override-User-Guide)
- See [framos-jetson-libsv](https://github.com/framosimaging/framos-jetson-libsv/tree/l4t-r36.4.4) GitHub

***When using the IMX636 event based sensor, use [OpenEB software GitHub](https://github.com/framosimaging/openeb)


# For detailed guide and additional options and descriptions - [FRAMOS Sensor Module Ecosystem ‐ Driver User Guide](https://github.com/framosimaging/framos-jetson-drivers/wiki/FRAMOS-Sensor-Module-Ecosystem-%E2%80%90-Driver-User-Guide)
