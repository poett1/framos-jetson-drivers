# Camera hardware tests

pytest suite that checks a FRAMOS camera setup on the Jetson itself: board and
modules, device tree, sensor probe, V4L2 controls, raw streaming, frame content,
`v4l2-compliance` and Argus. What a setup should look like is described by a
profile in `profiles/`, one per board and camera connection.

## Dependencies

| | Jetpack 7 (Ubuntu 24.04) | Jetpack 6 (Ubuntu 22.04) | Yocto (OE4T) |
|---|---|---|---|
| pytest | `python3-pytest` (7.4) | `python3-pytest` (6.2) | `python3-pytest` |
| YAML | `python3-yaml` | `python3-yaml` | `python3-pyyaml` |
| V4L2 tools | `v4l-utils` | `v4l-utils` | `v4l-utils` |
| Argus | `gstreamer1.0-tools`, `nvidia-l4t-gstreamer` (stock image) | same | `gstreamer1.0`, `gstreamer1.0-plugins-nvarguscamerasrc` |

```
sudo apt-get install python3-pytest python3-yaml v4l-utils
```

Install from the distribution, not with pip.

## Running

The tests run as root (kernel log, `nvargus-daemon`). From the repository root:

```
sudo python3 -m pytest tests/hw --profile=tests/hw/profiles/agx-fpa4a-j5-direct-imx900-4lane.yaml
```

Selecting tests:

```
sudo python3 -m pytest tests/hw --profile=... -m "not argus"      # leave out a group
sudo python3 -m pytest tests/hw --profile=... -k "10-bit"         # one mode
sudo python3 -m pytest tests/hw --profile=... --lf                # rerun the last failures
sudo python3 -m pytest tests/hw --profile=... --junitxml out.xml  # JUnit XML
python3 -m pytest tests/hw -m unit                                # no hardware, no root
```

Groups (markers), in run order: `env`, `dt`, `probe`, `controls`, `stream`,
`image`, `argus`, `compliance`. `v4l2-compliance` sets controls to test values
(for example `operation_mode` to Slave Mode, after which the IMX900 sends no
frames); the suite restores them afterwards and runs compliance last.

Tests that need the camera are skipped, not
failed, when the sensor did not probe.

At the end, the suite prints a Markdown table (for the test reports) and writes
`results.json` and `summary.md` to `tests/hw/results/<profile>-<date>/`, or to
`--results-dir`.

## Profiles

One profile per boot configuration: the suite does not change overlays, so
reboot into the configuration a profile describes before running it.

| Profile | Board | Camera connection |
|---|---|---|
| `agx-fpa4a-j5-direct-imx900-4lane` | AGX Orin devkit, Jetpack 7.2.1 | FPA-4.A/AGX J5, direct |
| `nano-p3768-cam1-direct-imx900-4lane` | Orin Nano Super devkit, Jetpack 7.2.1 | FPA-A/P22 cam1, direct |
| `nano-p3768-cam1-gmsl-imx900-4lane` | Orin Nano Super devkit, Jetpack 7.2.1 | FPA-A/P22 cam1, GMSL3 |
| `nx-p3768-cam1-direct-imx900-4lane` | Orin NX on p3768, Jetpack 7.2.1 | FPA-A/P22 cam1, direct |
| `nx-p3768-cam1-gmsl-imx900-4lane` | Orin NX on p3768, Jetpack 7.2.1 | FPA-A/P22 cam1, GMSL3 |
| `nano-p3768-cam1-gmsl-imx900-4lane-jp6` | Orin Nano Super devkit, Jetpack 6 (FRAMOS l4t-r36.4.4) | FPA-A/P22 cam1, GMSL3 (reference) |

Optional profile keys:

- `argus_tuning: nito | isp` (default `nito`): with `nito`, the Argus tests need
  `/var/nvidia/nvcam/settings/<badge>.nito` (Jetpack 7.2); with `isp`, they run
  with the `.isp` override (Jetpack 6).
- `known_failures: {"<file>::<test>": "<reason>"}`: these tests are expected to
  fail (strict xfail). If one starts passing, the run fails and says so; remove
  the entry.
- `stream: {frames, window, rate_tolerance}`, `image: {min_stddev}`: pass
  criteria, defaults 450 / 300 / 0.02 and 1.0.

Pass `--profile=<path>` with `=`: pytest treats a separate path argument as a
place to look for its configuration.

## v4l2-compliance baselines

NVIDIA's VI driver fails parts of `v4l2-compliance` by design, so a plain
pass/fail would always be red. `compliance-baselines/<profile>.txt` lists the
accepted failures, one `<node>: <test name>` per line (`node` is `video`,
`subdev` or `media`), each with a `# reason`.

- `test_no_new_failures[video|subdev|media]` fails on a failure that is not in
  the baseline.
- `test_known_failure[<node>: <test>]`, one per baseline line, reports XFAIL
  while the failure persists. When it starts passing, the run fails
  (strict XPASS): remove the line.

For a new profile, or after a driver change that is meant to change the result:

```
sudo python3 -m pytest tests/hw --profile=... -m compliance --write-compliance-baseline
```

This writes the baseline from the run (the run itself still fails without a
baseline). Add a `# reason` to every line, say whether it is an NVIDIA VI
limitation or a FRAMOS driver issue, review, and commit. The video and subdev
nodes are tested with `-d`/`-u`, the media device with `-M` (media device only).

## Boot-state test

`controls` checks the control values right after boot. A second full run
without a reboot fails it, because the first run changed the controls. Use
`-m "not controls"` for reruns.
