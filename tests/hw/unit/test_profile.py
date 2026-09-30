from pathlib import Path

import pytest

from lib.profile import ProfileError, load_profile

pytestmark = pytest.mark.unit

PROFILE_DIR = Path(__file__).parents[1] / "profiles"
PROFILES = sorted(PROFILE_DIR.glob("*.yaml"))
AGX = PROFILE_DIR / "agx-fpa4a-j5-direct-imx900-4lane.yaml"


def test_all_shipped_profiles_load():
    assert len(PROFILES) == 7
    for p in PROFILES:
        prof = load_profile(p)
        assert prof["name"] == p.stem
        assert prof["stream"] == {"frames": 450, "window": 300, "rate_tolerance": 0.02}
        assert prof["image"] == {"min_stddev": 1.0}
        assert prof["argus_tuning"] in ("nito", "isp")
        assert isinstance(prof["known_failures"], dict)


def test_missing_key_names_it(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(AGX.read_text().replace("badge: imx900_bottomleft_framos\n", ""))
    with pytest.raises(ProfileError, match=r"x\.yaml.*badge"):
        load_profile(p)


def test_wrong_type_names_path(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(AGX.read_text().replace("max_fps: 117.0", "max_fps: fast", 1))
    with pytest.raises(ProfileError, match=r"v4l2_modes\[1\]\.max_fps"):
        load_profile(p)


def test_empty_compatible_list_rejected(tmp_path):
    p = tmp_path / "x.yaml"
    text = AGX.read_text()
    start = text.index("dt_compatible:")
    end = text.index("\n", start)
    p.write_text(text[:start] + "dt_compatible: []" + text[end:])
    with pytest.raises(ProfileError, match="dt_compatible"):
        load_profile(p)


def test_gmsl_profile_lists_serdes_modules():
    prof = load_profile(PROFILE_DIR / "nano-p3768-cam1-gmsl-imx900-4lane.yaml")
    assert prof["gmsl"] is True
    assert {"fr_max96792", "fr_max96793"} <= set(prof["modules"])


def test_bad_argus_tuning_rejected(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(AGX.read_text().replace("argus_tuning: nito", "argus_tuning: cfg"))
    with pytest.raises(ProfileError, match="argus_tuning"):
        load_profile(p)


def test_jp6_reference_profile():
    prof = load_profile(PROFILE_DIR / "nano-p3768-cam1-gmsl-imx900-4lane-jp6.yaml")
    assert prof["argus_tuning"] == "isp"
    assert "test_04_controls.py::test_defaults_after_boot" in prof["known_failures"]
