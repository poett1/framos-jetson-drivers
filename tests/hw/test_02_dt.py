"""Live device tree: sensor node, SerDes clock property, module badge."""

import pytest

from lib import dt

pytestmark = pytest.mark.dt


def test_sensor_node_okay(profile):
    path = profile["sensor_dt_path"]
    assert dt.read_str(f"{path}/compatible") is not None, f"no sensor node at {path}"
    assert dt.read_str(f"{path}/status") in (None, "okay"), f"{path} is not enabled"


def test_serdes_pix_clk(profile):
    path = profile["sensor_dt_path"]
    modes = [m for m in dt.children(path) if m.startswith("mode")]
    assert modes, f"no mode nodes under {path}"
    have = [m for m in modes if dt.read_str(f"{path}/{m}/serdes_pix_clk_hz") is not None]
    if profile["gmsl"]:
        assert have == modes, f"GMSL: serdes_pix_clk_hz missing in {sorted(set(modes) - set(have))}"
    else:
        assert have == [], f"direct: serdes_pix_clk_hz not removed from {have}"


def test_badge(profile):
    badges = dt.active_badges()
    assert profile["badge"] in badges, f"badge {profile['badge']} not among {badges}"
