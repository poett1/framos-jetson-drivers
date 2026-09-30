"""Argus capture through nvarguscamerasrc, and the nvargus-daemon log."""

import re
from pathlib import Path

SETTINGS_DIR = Path("/var/nvidia/nvcam/settings")
FPS_RE = re.compile(r"average:\s*([\d.]+)")
ARGUS_ERROR_RE = re.compile(r"NitoPath|Could not map module|knobSetId \d+ not found|"
                            r"NvCameraIsp\w* .*error|SCF: Error|\(NvCamV4l2\) Error", re.I)


def tuning_file(profile, settings_dir=SETTINGS_DIR):
    """The tuning file Argus reads for this profile: <badge>.nito (Jetpack 7.2)
    or the camera_overrides.isp override (Jetpack 6)."""
    if profile["argus_tuning"] == "nito":
        return Path(settings_dir) / f"{profile['badge']}.nito"
    return Path(settings_dir) / "camera_overrides.isp"


def pipeline(mode, sensor_id=0, buffers=400):
    caps = (f"video/x-raw(memory:NVMM),width={mode['width']},height={mode['height']},"
            f"framerate={round(mode['max_fps'])}/1")
    return ["gst-launch-1.0", "-v", "nvarguscamerasrc", f"sensor-id={sensor_id}",
            f"sensor-mode={mode['sensor_mode']}", f"num-buffers={buffers}", "!", caps, "!",
            "fpsdisplaysink", "video-sink=fakesink", "text-overlay=false", "sync=false"]


def parse_fps(text):
    """Last average rate reported by fpsdisplaysink, None if there is none."""
    values = FPS_RE.findall(text)
    return float(values[-1]) if values else None


def daemon_errors(log):
    return [line.strip() for line in log.splitlines() if ARGUS_ERROR_RE.search(line)]
