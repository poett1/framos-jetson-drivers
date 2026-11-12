"""Argus capture through nvarguscamerasrc, and the nvargus-daemon log."""

import re
import statistics
from pathlib import Path

SETTINGS_DIR = Path("/var/nvidia/nvcam/settings")
CURRENT_RE = re.compile(r"current:\s*([\d.]+)")
WARMUP_INTERVALS = 4  # fpsdisplaysink reports every 0.5 s: skip the first 2 s
ARGUS_ERROR_RE = re.compile(r"NitoPath|knobSetId \d+ not found|"
                            r"NvCameraIsp\w* .*error|SCF: Error|\(NvCamV4l2\) Error", re.I)


def tuning_file(profile, settings_dir=SETTINGS_DIR):
    """The tuning file Argus reads for this profile: <badge>.nito (Jetpack 7.2)
    or the camera_overrides.isp override (Jetpack 6)."""
    if profile["argus_tuning"] == "nito":
        return Path(settings_dir) / f"{profile['badge']}.nito"
    return Path(settings_dir) / "camera_overrides.isp"


def pipeline(mode, sensor_id=0, seconds=6):
    """gst-launch-1.0 command streaming about `seconds` at the mode's rate."""
    buffers = max(400, round(mode["max_fps"] * seconds))
    caps = (f"video/x-raw(memory:NVMM),width={mode['width']},height={mode['height']},"
            f"framerate={round(mode['max_fps'])}/1")
    return ["gst-launch-1.0", "-v", "nvarguscamerasrc", f"sensor-id={sensor_id}",
            f"sensor-mode={mode['sensor_mode']}", f"num-buffers={buffers}", "!", caps, "!",
            "fpsdisplaysink", "video-sink=fakesink", "text-overlay=false", "sync=false"]


def parse_fps(text):
    """Frame rate from fpsdisplaysink: median of the per-interval "current" rates after
    a 2 s warm-up (the cumulative "average" includes the startup burst). None if there
    is no report."""
    values = [float(v) for v in CURRENT_RE.findall(text)]
    if not values:
        return None
    steady = values[WARMUP_INTERVALS:]
    return statistics.median(steady if len(steady) >= 3 else values)


def daemon_errors(log):
    return [line.strip() for line in log.splitlines() if ARGUS_ERROR_RE.search(line)]


def daemon_log_cmd(invocation_id):
    """journalctl command for the log of one nvargus-daemon start (systemd's
    InvocationID), without what the previous instance logged while stopping."""
    return ["journalctl", f"_SYSTEMD_INVOCATION_ID={invocation_id}", "-o", "cat", "--no-pager"]


def failure_report(summary, output, errors, lines=30):
    """Summary, the last lines of the gst-launch output (stdout and stderr) and the
    nvargus-daemon errors, for an assertion message."""
    tail = "\n".join(output.strip().splitlines()[-lines:])
    report = f"{summary}\n--- gst-launch-1.0 (last {lines} lines):\n{tail}"
    if errors:
        report += "\n--- nvargus-daemon:\n" + "\n".join(errors[:20])
    return report
