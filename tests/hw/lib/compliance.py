"""v4l2-compliance runs and the per-profile baselines of accepted failures."""

import re
import subprocess
from pathlib import Path

from lib.sysinfo import hand_back, make_dirs

# -M: the media device only; -m would also test every interface again
NODES = {"video": "-d", "subdev": "-u", "media": "-M"}
BASELINE_DIR = Path(__file__).resolve().parents[1] / "compliance-baselines"
TEST_RE = re.compile(r"^\s*test (.+?): (OK|FAIL)(?: \((.*)\))?\s*$")


class BaselineMissing(Exception):
    pass


def run(kind, devnode):
    """v4l2-compliance output for one node, whatever its exit code."""
    return subprocess.run(["v4l2-compliance", NODES[kind], devnode], capture_output=True,
                          text=True, timeout=300).stdout


def parse(text):
    """{test name: "OK" | "FAIL" | "OK (<note>)"}; a name that repeats keeps FAIL."""
    results = {}
    for line in text.splitlines():
        m = TEST_RE.match(line)
        if not m:
            continue
        status = m.group(2) + (f" ({m.group(3)})" if m.group(3) else "")
        if results.get(m.group(1)) != "FAIL":
            results[m.group(1)] = status
    return results


def failures(results):
    return [name for name, status in results.items() if status == "FAIL"]


def baseline_path(profile_name):
    return BASELINE_DIR / f"{profile_name}.txt"


def read_baseline(path):
    """{kind: {test name}}, None if there is no baseline file."""
    try:
        text = Path(path).read_text()
    except FileNotFoundError:
        return None
    baseline = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if ": " in line:
            kind, name = line.split(": ", 1)
            baseline.setdefault(kind.strip(), set()).add(name.strip())
    return baseline


def write_baseline(path, fails, header):
    lines = [header.rstrip("\n"), ""]
    for kind in sorted(fails):
        lines += [f"{kind}: {name}" for name in sorted(fails[kind])]
    created = make_dirs(Path(path).parent)
    Path(path).write_text("\n".join(lines) + "\n")
    hand_back(*created, path)


def new_failures(kind, results, baseline, path):
    """Failures of one node that the baseline does not accept."""
    if baseline is None:
        raise BaselineMissing(f"no baseline {path}; run with -m compliance "
                              f"--write-compliance-baseline, review, commit")
    return sorted(set(failures(results)) - baseline.get(kind, set()))


def known_failure_params(baseline):
    return sorted((kind, name) for kind, names in (baseline or {}).items() for name in names)
