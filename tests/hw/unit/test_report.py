import json
import re
import subprocess
from pathlib import Path

import pytest

from lib.report import TestResult, render_markdown, write_results
from lib.sysinfo import repo_commit

pytestmark = pytest.mark.unit


def test_markdown_table_rows():
    md = render_markdown({"profile": "p", "commit": "abc"},
                         [TestResult("t.py::test_a[10-bit full]", "passed", 1.0, {"fps": 117.02}, ""),
                          TestResult("t.py::test_b", "skipped", 0.0, {}, "no nito\nmore")])
    assert "| test_a[10-bit full] | PASS | fps=117.02 |" in md
    assert "| test_b | SKIP | no nito |" in md
    assert "Profile: p" in md and "Kernel: -" in md


def test_write_results(tmp_path):
    write_results(tmp_path, {"profile": "p"}, [TestResult("a", "failed", 2.0, {}, "boom")])
    data = json.loads((tmp_path / "results.json").read_text())
    assert data["meta"]["profile"] == "p" and data["results"][0]["outcome"] == "failed"
    assert (tmp_path / "summary.md").exists()


def _repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "f").write_text("1")
    subprocess.run(["git", "-C", str(tmp_path), "add", "f"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.email=a@b", "-c", "user.name=a",
                    "commit", "-q", "-m", "x"], check=True)
    return tmp_path


def test_repo_commit_clean_and_dirty(tmp_path):
    repo = _repo(tmp_path)
    assert re.fullmatch(r"[0-9a-f]{7,}", repo_commit(repo))
    (repo / "f").write_text("2")
    assert repo_commit(repo).endswith("-dirty")


def test_repo_commit_of_this_checkout():          # Review Focus 1 when run via sudo
    assert repo_commit(Path(__file__).parents[3]) != "unknown"


def test_failed_row_shows_properties_and_message():
    md = render_markdown({}, [TestResult("t.py::test_c", "failed", 0.1, {"install_type": "nvidia-stock"},
                                         "AssertionError: stock camera core\nmore")])
    assert "| test_c | FAIL | install_type=nvidia-stock; AssertionError: stock camera core |" in md
