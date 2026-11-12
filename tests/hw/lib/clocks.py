"""VIC clock (devfreq) for the Argus tests.

nvarguscamerasrc converts each frame on VIC. On stock Jetpack 7.2.1 the VIC
governor (tegra_wmark) settles at 166-192 MHz during a 2064x1552 capture, and
Argus then delivers every second frame (DT mode 6, 2064x1552 10-bit: 58.5
instead of 117 fps; mode 5 before the 2048x1536 modes were added). With
VIC at its maximum the rate is 117 fps; the libargus samples without GStreamer
reach 117 fps at the default clock."""

from pathlib import Path

DEVFREQ_DIR = Path("/sys/class/devfreq")


def find_vic(devfreq_dir=DEVFREQ_DIR):
    """The VIC devfreq directory (<addr>.vic), or None."""
    found = sorted(Path(devfreq_dir).glob("*.vic"))
    return found[0] if found else None


def _read(dev, name):
    return int((Path(dev) / name).read_text())


def pin_max(dev):
    """Set min_freq to max_freq; returns the previous min_freq for restore_min()."""
    before = _read(dev, "min_freq")
    (Path(dev) / "min_freq").write_text(str(_read(dev, "max_freq")))
    return before


def restore_min(dev, min_freq):
    (Path(dev) / "min_freq").write_text(str(min_freq))
