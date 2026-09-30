"""Loading and checking of the per-board test profiles (profiles/*.yaml)."""

from pathlib import Path

import yaml

DEFAULTS = {
    "stream": {"frames": 450, "window": 300, "rate_tolerance": 0.02},
    "image": {"min_stddev": 1.0},
    "argus_tuning": "nito",
    "known_failures": {},
}

V4L2_MODE = {"name": str, "pixelformat": str, "width": int, "height": int, "max_fps": float}
ARGUS_MODE = {"sensor_mode": int, "width": int, "height": int, "max_fps": float}


class ProfileError(Exception):
    pass


def _check(value, kind, where, errors):
    if kind is float:
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif kind is int:
        ok = isinstance(value, int) and not isinstance(value, bool)
    else:
        ok = isinstance(value, kind)
    if not ok:
        errors.append(f"{where}: expected {kind.__name__}, got {value!r}")
    return ok


def _check_list(prof, key, item, errors):
    items = prof.get(key)
    if not _check(items, list, key, errors):
        return
    for i, entry in enumerate(items):
        where = f"{key}[{i}]"
        if not _check(entry, dict, where, errors):
            continue
        for field, kind in item.items():
            if field not in entry:
                errors.append(f"{where}.{field}: missing")
            else:
                _check(entry[field], kind, f"{where}.{field}", errors)


def load_profile(path):
    """Load a profile, check keys and types, fill defaults. Raises ProfileError."""
    path = Path(path)
    try:
        prof = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as e:
        raise ProfileError(f"{path}: {e}") from e
    if not isinstance(prof, dict):
        raise ProfileError(f"{path}: not a mapping")

    errors = []
    for key, kind in (("name", str), ("gmsl", bool), ("sensor_dt_path", str),
                      ("devname", str), ("badge", str)):
        if key not in prof:
            errors.append(f"{key}: missing")
        else:
            _check(prof[key], kind, key, errors)
    for key in ("dt_compatible", "modules"):
        if key not in prof:
            errors.append(f"{key}: missing")
        elif _check(prof[key], list, key, errors):
            if key == "dt_compatible" and not prof[key]:
                errors.append(f"{key}: must not be empty")
            for i, v in enumerate(prof[key]):
                _check(v, str, f"{key}[{i}]", errors)
    if isinstance(prof.get("sensor_dt_path"), str) and not prof["sensor_dt_path"].startswith("/"):
        errors.append("sensor_dt_path: must start with /")
    defaults = (prof.get("controls") or {}).get("defaults")
    if _check(defaults, dict, "controls.defaults", errors):
        for k, v in defaults.items():
            _check(v, int, f"controls.defaults.{k}", errors)
    _check_list(prof, "v4l2_modes", V4L2_MODE, errors)
    _check_list(prof, "argus_modes", ARGUS_MODE, errors)
    if prof.get("argus_tuning", "nito") not in ("nito", "isp"):
        errors.append(f"argus_tuning: must be nito or isp, got {prof['argus_tuning']!r}")
    _check(prof.get("known_failures", {}), dict, "known_failures", errors)
    if errors:
        raise ProfileError(f"{path}: " + "; ".join(errors))

    for key, value in DEFAULTS.items():
        if isinstance(value, dict) and key in ("stream", "image"):
            prof[key] = {**value, **(prof.get(key) or {})}
        else:
            prof.setdefault(key, value)
    return prof
