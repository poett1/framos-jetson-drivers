"""Facts about the board and the checkout under test."""

import os
import re
import subprocess
from pathlib import Path


def repo_commit(repo):
    """Short commit of the checkout, "-dirty" if tracked files changed, "unknown" on error.

    safe.directory lets root (sudo pytest) read a checkout owned by the user."""
    git = ["git", "-c", f"safe.directory={repo}", "-C", str(repo)]
    try:
        commit = subprocess.run(git + ["rev-parse", "--short", "HEAD"], capture_output=True,
                                text=True, check=True).stdout.strip()
        dirty = subprocess.run(git + ["status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return commit + ("-dirty" if dirty else "")


def l4t_release(text):
    """ "# R39 (release), REVISION: 2.1, ..." (/etc/nv_tegra_release) -> "39.2.1" """
    m = re.search(r"# R(\d+) \(release\), REVISION: ([\d.]+)", text)
    return f"{m.group(1)}.{m.group(2)}" if m else "unknown"


def install_type(kallsyms, tegra_camera_path):
    """How the camera core got there: "framos-depmod" (target_build.sh install into
    updates/framos), "framos-in-tree" (FRAMOS camera core elsewhere, e.g. Yocto or
    Jetpack 6 modules_install) or "nvidia-stock" (no FRAMOS camera core loaded)."""
    if not re.search(r"\bregmap_util_write_table_32\b", kallsyms):
        return "nvidia-stock"
    return "framos-depmod" if "/updates/framos/" in tegra_camera_path else "framos-in-tree"


def hand_back(*paths):
    """Give files written by `sudo pytest` to the user who ran sudo, so the checkout
    stays usable without root (git pull, rm). No-op when not running under sudo."""
    uid, gid = os.environ.get("SUDO_UID"), os.environ.get("SUDO_GID")
    if os.geteuid() != 0 or not uid or not gid:
        return
    for path in paths:
        try:
            os.chown(path, int(uid), int(gid))
        except OSError:
            pass


def make_dirs(path):
    """Create `path` and missing parents; return the directories created, outermost first
    (only those may be handed back: never an existing directory such as /tmp)."""
    path = Path(path)
    missing = []
    while not path.exists():
        missing.append(path)
        path = path.parent
    for d in reversed(missing):
        d.mkdir(exist_ok=True)
    return list(reversed(missing))
