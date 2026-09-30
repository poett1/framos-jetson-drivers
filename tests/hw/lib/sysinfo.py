"""Facts about the board and the checkout under test."""

import subprocess


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
