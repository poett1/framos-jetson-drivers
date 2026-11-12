"""FRAMOS camera hardware tests: options, profile, results reporting.

Run: sudo python3 -m pytest tests/hw --profile tests/hw/profiles/<name>.yaml
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

HW_DIR = Path(__file__).resolve().parent
REPO_DIR = HW_DIR.parents[1]
sys.path.insert(0, str(HW_DIR))  # "lib" package; pytest 6.2 has no pythonpath ini option

from lib.profile import ProfileError, load_profile  # noqa: E402
from lib.report import TestResult, render_markdown, write_results  # noqa: E402
from lib import argus, clocks, compliance, dt, kmsg, media, v4l2  # noqa: E402
from lib.sysinfo import install_type, l4t_release, repo_commit  # noqa: E402

# per-session state; pytest 6.2 has no config.stash
SESSION = {"profile": None, "meta": {}, "results": [], "results_dir": None, "compliance": None}


def pytest_addoption(parser):
    group = parser.getgroup("framos")
    group.addoption("--profile", help="board profile (tests/hw/profiles/*.yaml)")
    group.addoption("--results-dir",
                    help="where results.json and summary.md go "
                         "(default tests/hw/results/<profile>-<date>)")
    group.addoption("--write-compliance-baseline", action="store_true",
                    help="write compliance-baselines/<profile>.txt from this run")


def pytest_configure(config):
    SESSION.update(profile=None, meta={}, results=[], results_dir=None, compliance=None)
    path = config.getoption("--profile")
    if not path:
        return
    try:
        prof = load_profile(path)
    except ProfileError as e:
        raise pytest.UsageError(str(e))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    SESSION["profile"] = prof
    SESSION["meta"].update(profile=prof["name"], commit=repo_commit(REPO_DIR),
                           date=time.strftime("%Y-%m-%d %H:%M:%S"))
    SESSION["results_dir"] = Path(config.getoption("--results-dir")
                                  or HW_DIR / "results" / f"{prof['name']}-{stamp}")


def _known_failure(nodeid, known):
    for key, reason in known.items():
        if nodeid == key or nodeid.startswith(key + "[") or nodeid.endswith("/" + key):
            return reason
    return None


def pytest_collection_modifyitems(config, items):
    prof = SESSION["profile"]
    if not prof:
        return
    for item in items:
        reason = _known_failure(item.nodeid, prof["known_failures"])
        if reason:
            item.add_marker(pytest.mark.xfail(strict=True, reason=f"known failure: {reason}"))
        reason = _known_failure(item.nodeid, prof["flaky"])
        if reason:
            # intermittent: a pass (XPASS) and a failure (XFAIL) are both reported, neither fails the run
            item.add_marker(pytest.mark.xfail(strict=False, reason=f"flaky: {reason}"))


def pytest_generate_tests(metafunc):
    """One test per profile mode: v4l2_mode (ids = mode name), argus_mode (ids = modeN)."""
    prof = SESSION["profile"]
    for arg, key, ident in (("v4l2_mode", "v4l2_modes", lambda m: m["name"]),
                            ("argus_mode", "argus_modes", lambda m: f"mode{m['sensor_mode']}")):
        if arg in metafunc.fixturenames:
            modes = prof[key] if prof else [None]
            metafunc.parametrize(arg, modes, ids=[ident(m) if m else "no-profile" for m in modes])
    if "known_failure" in metafunc.fixturenames:
        path = compliance.baseline_path(prof["name"]) if prof else None
        baseline = compliance.read_baseline(path) if prof else None
        params = [pytest.param(p, id=f"{p[0]}: {p[1]}")
                  for p in compliance.known_failure_params(baseline)]
        if not params:
            reason = ("no --profile given" if not prof else f"no baseline {path}"
                      if baseline is None else "the baseline lists no accepted failures")
            params = [pytest.param(None, id="none", marks=pytest.mark.skip(reason=reason))]
        metafunc.parametrize("known_failure", params)


@pytest.fixture(scope="session")
def profile():
    if SESSION["profile"] is None:
        pytest.skip("no --profile given")
    return SESSION["profile"]


@pytest.fixture(scope="session")
def meta():
    """Run facts shown in the summary header; fixtures of later groups add to it."""
    return SESSION["meta"]


def _read(path):
    try:
        return Path(path).read_text()
    except OSError:
        return ""


@pytest.fixture(scope="session")
def board(profile, meta):
    """Board facts; the L4T release, kernel and install type also go into the summary."""
    tegra_camera = subprocess.run(["modinfo", "-n", "tegra_camera"], capture_output=True,
                                  text=True).stdout.strip()
    facts = {
        "compatible": dt.read_strlist("/compatible"),
        "model": dt.read_str("/model"),
        "l4t": l4t_release(_read("/etc/nv_tegra_release")),
        "kernel": os.uname().release,
        "install_type": install_type(_read("/proc/kallsyms"), tegra_camera),
    }
    meta.update(l4t=facts["l4t"], kernel=facts["kernel"], install_type=facts["install_type"])
    return facts


@pytest.fixture(scope="session")
def sensor(profile):
    """Video, subdev and media nodes of the profile's sensor; skips if it did not probe."""
    nodes = media.find_sensor_nodes(profile["devname"])
    if nodes is None:
        pytest.skip(f"sensor not probed: {profile['devname']} not in any media graph")
    return nodes


@pytest.fixture
def dmesg_mark():
    """Returns a callable giving the CSI/PHY/RCE errors logged since the test started."""
    before = kmsg.kernel_log()
    return lambda: kmsg.new_errors(before, kmsg.kernel_log())


@pytest.fixture(scope="session")
def compliance_results(sensor):
    """v4l2-compliance of the video node, sensor subdev and media device, run once."""
    nodes = {"video": sensor.video, "subdev": sensor.subdev, "media": sensor.media}
    # v4l2-compliance leaves controls at test values (seen: operation_mode = Slave Mode,
    # after which the sensor sends no frames), so put them back afterwards
    before = v4l2.snapshot_ctrls(sensor.video)
    SESSION["compliance_output"] = {kind: compliance.run(kind, dev) for kind, dev in nodes.items()}
    SESSION["compliance"] = {kind: compliance.parse(out)
                             for kind, out in SESSION["compliance_output"].items()}
    left = v4l2.restore_ctrls(sensor.video, before)
    if left:
        raise RuntimeError(f"controls not restored after v4l2-compliance: {left}")
    return SESSION["compliance"]


@pytest.fixture
def vic_max():
    """Pins the VIC clock at its maximum during the test and returns it in MHz (None if
    the board has no VIC devfreq). At the governor's default clock nvarguscamerasrc
    delivers only every second frame of fast modes, see lib/clocks.py."""
    dev = clocks.find_vic()
    if dev is None:
        yield None
        return
    before = clocks.pin_max(dev)
    try:
        yield int((dev / "min_freq").read_text()) // 1000000
    finally:
        clocks.restore_min(dev, before)


@pytest.fixture
def argus_daemon(sensor):
    """Restarts nvargus-daemon for each test (a failed capture session can leave it
    unusable); returns a callable giving the new daemon's log (by systemd
    InvocationID, so errors the old instance logs while stopping do not count).
    Leaves the daemon as it was found (stopped again if it was not running), and
    sets bypass_mode back to 0: Argus leaves it at 1, after which raw V4L2 streams
    get no frames."""
    was_active = subprocess.run(["systemctl", "is-active", "--quiet", "nvargus-daemon"]).returncode == 0
    subprocess.run(["systemctl", "restart", "nvargus-daemon"], check=True)
    invocation = subprocess.run(["systemctl", "show", "-p", "InvocationID", "--value",
                                 "nvargus-daemon"], capture_output=True, text=True,
                                check=True).stdout.strip()
    time.sleep(2)
    yield lambda: subprocess.run(argus.daemon_log_cmd(invocation), capture_output=True,
                                 text=True).stdout
    v4l2.set_ctrl(sensor.video, "bypass_mode", 0)
    if not was_active:
        subprocess.run(["systemctl", "stop", "nvargus-daemon"])


def pytest_sessionfinish(session):
    if session.config.getoption("--write-compliance-baseline") and SESSION["compliance"]:
        meta = SESSION["meta"]
        path = compliance.baseline_path(meta["profile"])
        header = (f"# v4l2-compliance failures accepted for {meta['profile']}\n"
                  f"# written {meta.get('date')} from commit {meta.get('commit')}, "
                  f"L4T {meta.get('l4t')}; add '# reason' to each line")
        compliance.write_baseline(path, {k: compliance.failures(r)
                                         for k, r in SESSION["compliance"].items()}, header)
        session.config.pluginmanager.get_plugin("terminalreporter").write_line(
            f"compliance baseline written: {path}")


def _message(report):
    if report.skipped and isinstance(report.longrepr, tuple):
        return report.longrepr[2].replace("Skipped: ", "", 1)
    crash = getattr(getattr(report, "longrepr", None), "reprcrash", None)
    if crash is not None:
        return crash.message
    return getattr(report, "wasxfail", "") or ""


def pytest_runtest_logreport(report):
    if "unit" in report.keywords:
        return  # hardware report only
    xfail = hasattr(report, "wasxfail")
    if report.when == "call":
        outcome = report.outcome
        if xfail:
            outcome = "xfailed" if report.skipped else "xpassed"
    elif report.when == "setup" and not report.passed:
        outcome = "xfailed" if (xfail and report.skipped) else (
            "skipped" if report.skipped else "error")
    elif report.when == "teardown" and report.failed:
        outcome = "error"
    else:
        return
    SESSION["results"].append(TestResult(report.nodeid, outcome, round(report.duration, 2),
                                         dict(report.user_properties), _message(report)))


def pytest_terminal_summary(terminalreporter):
    if SESSION["profile"] is None or not SESSION["results"]:
        return
    markdown = render_markdown(SESSION["meta"], SESSION["results"])
    write_results(SESSION["results_dir"], SESSION["meta"], SESSION["results"])
    terminalreporter.write_sep("=", "FRAMOS camera test summary")
    terminalreporter.write(markdown)
    terminalreporter.write_line(f"results: {SESSION['results_dir']}")
