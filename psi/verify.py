"""Self-verify gate — runs the generated scenario through the real run funnel.

Nothing the swarm generates is offered as a PR until it actually executes. This
spawns `scripts/run.py --tags <tag>` (the same funnel every run mode uses) and
parses the verdict. Returns (passed, output_tail).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_verify(tag: str, timeout: int = 600) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "scripts/run.py", "--tags", tag],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    m = re.search(r"Run verdict : (PASSED|FAILED)\s+\((\d+) passed, (\d+) failed", out)
    if not m:
        return False, out
    passed_verdict = m.group(1) == "PASSED"
    passed_n, failed_n = int(m.group(2)), int(m.group(3))
    return (passed_verdict and failed_n == 0 and passed_n >= 1), out
