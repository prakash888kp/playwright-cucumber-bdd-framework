"""Universal runner — every run mode funnels through here so a timestamped
report archive is ALWAYS produced, pass or fail.

  python scripts/run.py --tags "@smoke"
  python scripts/run.py --profile regression
  python scripts/run.py --excel
  python scripts/run.py --rerun

Exits with behave's exit code so CI still fails on test failures.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.config.env_loader import load_env  # noqa: E402

PROFILES = {
    "smoke": "@smoke",
    "regression": "@regression",
    "ui": "@ui",
    "api": "@api",
    "rag": "@rag",
}


def run_behave(tags: str | None = None) -> int:
    cmd = [
        sys.executable, "-m", "behave", "features",
        "-f", "json", "-o", "reports/behave-report.json",
        "-f", "pretty",
        "--no-capture",
    ]
    if tags:
        cmd += ["--tags", tags]
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    for stale in ("behave-report.json", "attachments.json"):
        (reports / stale).unlink(missing_ok=True)
    result = subprocess.run(cmd, cwd=ROOT)
    return result.returncode


def run_and_report(tags: str | None = None, run_args: str = "") -> int:
    os.environ["RUN_ARGS"] = run_args or (f"--tags {tags}" if tags else "(all)")
    exit_code = run_behave(tags)
    try:
        from framework.helpers.report_builder import build_report
        build_report()
    except Exception as exc:  # report failure must not mask the test verdict
        print(f"Report generation failed: {exc}", file=sys.stderr)
    return exit_code


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Framework run funnel")
    parser.add_argument("--tags", help='behave tag expression, e.g. "@smoke" or "@TC_UI_001 or @TC_API_001"')
    parser.add_argument("--profile", choices=sorted(PROFILES), help="named suite profile")
    parser.add_argument("--excel", action="store_true", help="run scenarios flagged Run=YES in execution-control.xlsx")
    parser.add_argument("--rerun", action="store_true", help="re-run failures from reports/rerun.txt")
    args = parser.parse_args()

    if args.excel:
        from framework.runners.excel_runner import excel_tag_expression
        tags = excel_tag_expression()
        if not tags:
            print("No scenarios flagged Run = YES in execution-control.xlsx")
            return 0
        return run_and_report(tags, run_args=f"excel: {tags}")

    if args.rerun:
        rerun_file = ROOT / "reports" / "rerun.txt"
        failing = [t.strip() for t in rerun_file.read_text().splitlines() if t.strip()] if rerun_file.exists() else []
        if not failing:
            print("No failures recorded in reports/rerun.txt — nothing to re-run.")
            return 0
        tags = " or ".join(t if t.startswith("@") else f"@{t}" for t in failing)
        return run_and_report(tags, run_args=f"rerun: {tags}")

    tags = args.tags or (PROFILES[args.profile] if args.profile else os.environ.get("TAGS") or None)
    return run_and_report(tags, run_args=" ".join(sys.argv[1:]) or (f"TAGS={tags}" if tags else ""))


if __name__ == "__main__":
    sys.exit(main())
