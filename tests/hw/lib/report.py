"""Test results as a Markdown summary and results.json."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

OUTCOMES = {"passed": "PASS", "failed": "FAIL", "skipped": "SKIP",
            "xfailed": "XFAIL", "xpassed": "XPASS", "error": "ERROR"}
META_FIELDS = (("profile", "Profile"), ("commit", "Commit"), ("l4t", "L4T"),
               ("kernel", "Kernel"), ("install_type", "Install type"), ("date", "Date"))


@dataclass
class TestResult:
    __test__ = False  # not a pytest test class

    nodeid: str
    outcome: str
    duration: float
    properties: dict = field(default_factory=dict)
    message: str = ""


def _details(result):
    if result.properties:
        return ", ".join(f"{k}={v}" for k, v in result.properties.items())
    return result.message.strip().splitlines()[0] if result.message.strip() else ""


def render_markdown(meta, results):
    lines = [f"{label}: {meta.get(key) or '-'}  " for key, label in META_FIELDS]
    lines += ["", "| Test | Result | Details |", "|---|---|---|"]
    for r in results:
        name = r.nodeid.split("::", 1)[-1]
        details = _details(r).replace("|", "\\|")
        lines.append(f"| {name} | {OUTCOMES.get(r.outcome, r.outcome.upper())} | {details} |")
    return "\n".join(lines) + "\n"


def write_results(out_dir, meta, results):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = {"meta": meta, "results": [asdict(r) for r in results]}
    (out_dir / "results.json").write_text(json.dumps(data, indent=2, default=str) + "\n")
    (out_dir / "summary.md").write_text(render_markdown(meta, results))
