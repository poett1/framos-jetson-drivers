"""Board, L4T, loaded modules."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.env


def test_board_matches_profile(profile, board, record_property):
    record_property("model", board["model"])
    assert set(profile["dt_compatible"]) & set(board["compatible"]), \
        f"board compatible {board['compatible']} matches none of {profile['dt_compatible']}"


def test_modules_loaded(profile):
    loaded = {line.split()[0] for line in Path("/proc/modules").read_text().splitlines()}
    missing = [m for m in profile["modules"] if m.replace("-", "_") not in loaded]
    assert not missing, f"not loaded: {missing}"


def test_framos_camera_core(board, record_property):
    record_property("install_type", board["install_type"])
    assert board["install_type"] != "nvidia-stock", \
        "the loaded tegra_camera is NVIDIA's (no FRAMOS camera core); install and reboot"
