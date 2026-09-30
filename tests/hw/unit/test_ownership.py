import pytest

from lib import compliance, report

pytestmark = pytest.mark.unit


@pytest.fixture
def chowns(monkeypatch):
    calls = []
    monkeypatch.setattr("os.chown", lambda path, uid, gid: calls.append((str(path), uid, gid)))
    monkeypatch.setattr("os.geteuid", lambda: 0)
    monkeypatch.setenv("SUDO_UID", "1000")
    monkeypatch.setenv("SUDO_GID", "1001")
    return calls


def test_results_handed_back_to_sudo_user(tmp_path, chowns):
    out = tmp_path / "res" / "run"
    report.write_results(out, {"profile": "p"}, [])
    owned = {p for p, uid, gid in chowns if (uid, gid) == (1000, 1001)}
    assert {str(out), str(out / "results.json"), str(out / "summary.md")} <= owned


def test_baseline_handed_back_to_sudo_user(tmp_path, chowns):
    path = tmp_path / "compliance-baselines" / "p.txt"
    compliance.write_baseline(path, {"video": ["X"]}, "# h")
    owned = {p for p, uid, gid in chowns}
    assert {str(path.parent), str(path)} <= owned


def test_nothing_changed_without_sudo(tmp_path, chowns, monkeypatch):
    monkeypatch.delenv("SUDO_UID")
    report.write_results(tmp_path / "r", {}, [])
    assert chowns == []
