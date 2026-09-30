"""Reading the live device tree."""

from pathlib import Path

DT_ROOT = Path("/proc/device-tree")


def _read(path, root):
    try:
        return (Path(root) / path.lstrip("/")).read_bytes()
    except OSError:
        return None


def read_strlist(path, root=DT_ROOT):
    data = _read(path, root)
    return [s.decode(errors="replace") for s in data.split(b"\0") if s] if data else []


def read_str(path, root=DT_ROOT):
    """First string of a property, None if the property does not exist."""
    data = _read(path, root)
    if data is None:
        return None
    return data.split(b"\0", 1)[0].decode(errors="replace")


def children(path, root=DT_ROOT):
    node = Path(root) / path.lstrip("/")
    return sorted(p.name for p in node.iterdir() if p.is_dir()) if node.is_dir() else []


def active_badges(root=DT_ROOT):
    """Badges of the enabled tegra-camera-platform modules."""
    base = "/tegra-camera-platform/modules"
    badges = []
    for module in children(base, root):
        if read_str(f"{base}/{module}/status", root) in (None, "okay"):
            badge = read_str(f"{base}/{module}/badge", root)
            if badge:
                badges.append(badge)
    return badges
