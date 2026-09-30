"""Media controller graph (media-ctl -p)."""

import glob
import re
import subprocess
from dataclasses import dataclass, field


@dataclass
class Entity:
    name: str
    devnode: object = None  # str or None
    upstream: list = field(default_factory=list)  # names of enabled source entities


@dataclass
class SensorNodes:
    media: str
    subdev: str
    video: str


def parse_topology(text):
    entities = {}
    current = None
    for line in text.splitlines():
        m = re.match(r"^- entity \d+: (.+?) \(\d+ pads?", line)
        if m:
            current = entities.setdefault(m.group(1), Entity(m.group(1)))
            continue
        if current is None:
            continue
        m = re.search(r"device node name (\S+)", line)
        if m:
            current.devnode = m.group(1)
            continue
        m = re.search(r'<- "([^"]+)":\d+ \[([^\]]*)\]', line)
        if m and "ENABLED" in m.group(2):
            current.upstream.append(m.group(1))
    return entities


def topology_ok(entities, devname):
    """vi-output, <devname> <- nvcsi* <- <devname>, all links enabled."""
    vi = entities.get(f"vi-output, {devname}")
    if vi is None:
        return False
    for name in vi.upstream:
        csi = entities.get(name)
        if name.startswith("nvcsi") and csi is not None and devname in csi.upstream:
            return True
    return False


def find_sensor_nodes(devname):
    for media in sorted(glob.glob("/dev/media*")):
        out = subprocess.run(["media-ctl", "-d", media, "-p"], capture_output=True, text=True).stdout
        entities = parse_topology(out)
        sensor = entities.get(devname)
        vi = entities.get(f"vi-output, {devname}")
        if sensor and vi and sensor.devnode and vi.devnode:
            return SensorNodes(media, sensor.devnode, vi.devnode)
    return None
