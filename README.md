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
- Hardware-tested on 2026-09-28 on an Orin Nano devkit Super with a Yocto
  image, IMX900 over GMSL3. V4L2 controls are 64-bit (use `v4l2-ctl`, not
  `v4l2src extra-controls`).
- **Stock Jetpack 7.2.1** (Ubuntu 24.04, kernel `6.8.12-1021-tegra`): the
  drivers build and install on the Jetson itself with `build/target_build.sh`
  (next section). Hardware-tested on 2026-10-01 on an Orin Nano devkit Super
  with the IMX900 directly on FPA-A/P22 and over GMSL3: probe, raw V4L2 at
  72/117/125 fps and **Argus with a NITO file work** (10-bit full resolution at 117 fps needs a faster VIC clock, see below); see
  [TEST-RESULTS-l4t-r39.2.1.md](TEST-RESULTS-l4t-r39.2.1.md). On 2026-10-02
  the same on an AGX Orin devkit with the IMX900 on the FPA-4.A/AGX, J5
  ([TEST-RESULTS-l4t-r39.2.1-agx.md](TEST-RESULTS-l4t-r39.2.1-agx.md)).
- `tools/jetson-config-camera(-cli).py` work with the Jetpack 7 jetson-io and
  write a separate `FramosCamera` boot entry.
- `tests/hw/`: pytest suite for testing a camera setup on the Jetson, see
  [tests/hw/README.md](tests/hw/README.md).
- `isp/` and `firmware/` are carried unchanged from l4t-r36.4.4. The ISP
  override files are the Jetpack 6 ones (Jetpack 7.2 needs .nito files), and
  `build/cross-compile_build.sh` has not been adapted to 39.2.1.

## Build and install on stock Jetpack 7.2.1

On the Jetson, with this branch checked out:

```
sudo apt-get install build-essential device-tree-compiler \
    nvidia-l4t-kernel-headers nvidia-l4t-kernel-oot-headers
source build/target_build.sh      # prints the commands below
check                             # build all modules and overlays (about 3 min on AGX Orin)
install_all                       # install overlays and camera stack (sudo)
```

| Command | Does |
|---|---|
| `build_oot_modules`, `build_dtree`, `build_all` | build the OOT modules (NVIDIA's 39.2.1 top-level `source/Makefile`), the FRAMOS overlays, or both |
| `check` | refuses to build for a kernel other than the running one, then `build_all` |
| `install_dtree` | overlays to `/boot/framos/dtbo/` |
| `install_oot_modules` | the `fr_*` modules, `tegra-camera` and every stock module that depends on them (42 modules) to `/lib/modules/<kernel>/updates/framos/`, with `/etc/depmod.d/framos.conf` overriding the stock ones; first checks the symbol CRCs against the stock modules |
| `install_all` | both installs |
| `uninstall` | removes both; after a reboot the stock modules are used again |

The stock `.deb` files are not modified, so `apt upgrade` does not undo the
install; a kernel update needs a rebuild. The build warns that the compiler
(gcc 13.3) differs from the kernel's (gcc 13.2); that is expected with the
Ubuntu 24.04 toolchain.

Then select the camera configuration and reboot:

```
sudo python3 tools/jetson-config-camera-cli.py -n "Framos FPA-4.A/AGX" "Framos IMX900-J5-4Lane"
sudo python3 tools/jetson-config-camera.py      # interactive alternative
```

Both write a boot entry `FramosCamera` into `/boot/extlinux/extlinux.conf`
and make it the default. The stock `primary` entry is left unchanged and can
be picked in the boot menu.

For Argus, Jetpack 7.2 needs a NITO tuning file for the camera module's badge
in `/var/nvidia/nvcam/settings/`. `isp/` has two for the IMX900, converted from
`IMX900_IRC650.isp`:

```
sudo install -m 644 isp/imx900_rear_framos.nito /var/nvidia/nvcam/settings/        # Orin Nano/NX cam1
sudo install -m 644 isp/imx900_bottomleft_framos.nito /var/nvidia/nvcam/settings/  # AGX Orin FPA-4.A/AGX J5
```

Argus matches the badge stored inside the file, not the file name: a copy of
one NITO renamed to another badge is not found ("No cameras available"), and
editing the name inside makes it "corrupt". Each badge needs its own
conversion. NVIDIA's "Jetson Customer IQ Migration Tools" (camera hotfix,
`nvcfg2nito`) do that on the Jetson from a Jetpack 6 `.isp` override; they are
not part of this repository.

Both NITO files hold tuning only for the two modes they were converted with:
2064x1552 12-bit (`sensor-mode=0`) and 10-bit (`sensor-mode=6`). Argus gets no
frames in any other mode ("GetKnobSetIdFromSensorModeIndex ... not found"),
including the 2048x1536 modes (`sensor-mode=5`, 11, 17) and 1920x1080. Since
the 2048x1536 modes were added, 10-bit full resolution is `sensor-mode=6`
(it was 5), so pipelines that select mode 5 need updating.

At the default clocks, `nvarguscamerasrc` delivers IMX900 mode 6 (2064x1552
10-bit, 117 fps; mode 5 before the 2048x1536 modes were added) at 58.5 fps: the VIC clock, which converts each frame, stays
too low. `sudo jetson_clocks` (CPU, GPU and EMC at maximum; VIC then scales up
by itself) or pinning VIC alone gives 117 fps:

```
echo $(cat /sys/class/devfreq/15340000.vic/max_freq) | \
    sudo tee /sys/class/devfreq/15340000.vic/min_freq
```

Neither setting survives a reboot.

After an Argus session, set `v4l2-ctl -d /dev/video0 -c bypass_mode=0` before
capturing with raw V4L2 (Argus leaves it at 1, and raw V4L2 then gets no
frames).

Run `tests/hw` ([tests/hw/README.md](tests/hw/README.md)) on a freshly booted
board to check a setup. If a direct connection loses stream starts
(`corr_err` in the kernel log), try another flex cable first: at 2376
Mbps/lane a marginal cable shows up long before it does on a Raspberry Pi.

The procedure further below describes Jetpack 6.


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
