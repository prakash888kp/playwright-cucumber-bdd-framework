"""Report builder — called automatically after every run (all run modes).

Pure Python replacement for the old Node HTML reporter. Each run gets its
own archive folder so history is never overwritten:
  reports/run_2026-07-14_12-45-30_qa_PASSED/
    ├── html/index.html        rich self-contained dashboard (screenshots embedded)
    ├── behave-report.json     raw results for this run
    └── traces/                Playwright traces captured during this run

Also maintains reports/run-history.json + prints a summary, and writes
reports/latest-run.txt pointing at the newest archive.
"""
import base64
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from .logger import logger

ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "reports"
HISTORY_FILE = REPORTS_DIR / "run-history.json"
TEMPLATE_FILE = Path(__file__).parent / "report_template.html"


def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _scenario_status(element):
    return (element.get("status") or "unknown").lower()


def _filter_selected(features: list, attachments: dict) -> list:
    """Drop scenarios that were excluded by tag selection. behave reports them
    as "skipped", but hooks never ran for them — so unlike runtime skips
    (e.g. RAG without AWS creds) they have no key in the attachments manifest."""
    selected_features = []
    for feature in features:
        elements = [
            el
            for el in feature.get("elements", [])
            if el.get("type") == "background"
            or _scenario_status(el) not in ("skipped", "untested")
            or str(el.get("location", "")).replace("\\", "/") in attachments
        ]
        if any(el.get("type") != "background" for el in elements):
            selected_features.append({**feature, "elements": elements})
    return selected_features


def read_run_stats(features: list) -> dict:
    stats = {"features": len(features), "scenarios": 0, "passed": 0, "failed": 0, "skipped": 0}
    for feature in features:
        for element in feature.get("elements", []):
            if element.get("type") == "background":
                continue
            stats["scenarios"] += 1
            status = _scenario_status(element)
            if status == "failed":
                stats["failed"] += 1
            elif status in ("skipped", "untested"):
                stats["skipped"] += 1
            else:
                stats["passed"] += 1
    return stats


def _embed_attachments(attachments: dict) -> dict:
    """Convert screenshot file references into base64 data URIs so the
    report is a single self-contained HTML file."""
    embedded = {}
    for key, items in attachments.items():
        out = []
        for item in items:
            if item.get("type") == "image/png" and item.get("path"):
                png = REPORTS_DIR / item["path"]
                if png.exists():
                    b64 = base64.b64encode(png.read_bytes()).decode("ascii")
                    out.append({**item, "data": f"data:image/png;base64,{b64}", "path": None})
            else:
                out.append(item)
        embedded[key] = out
    return embedded


def build_report():
    json_file = REPORTS_DIR / "behave-report.json"
    if not json_file.exists():
        logger.error("No reports/behave-report.json found — nothing to report.")
        return None

    raw_attachments = _read_json(REPORTS_DIR / "attachments.json", {})
    features = _filter_selected(_read_json(json_file, []), raw_attachments)
    stats = read_run_stats(features)
    verdict = "FAILED" if stats["failed"] > 0 else "PASSED"
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    env = os.environ.get("ENV", "qa")
    run_dir = REPORTS_DIR / f"run_{stamp}_{env}_{verdict}"
    (run_dir / "html").mkdir(parents=True, exist_ok=True)

    # Archive this run's raw artifacts
    shutil.copy2(json_file, run_dir / "behave-report.json")
    traces_dir = REPORTS_DIR / "traces"
    if traces_dir.exists() and any(traces_dir.iterdir()):
        shutil.move(str(traces_dir), str(run_dir / "traces"))

    # Attachments (per-step screenshots, RAG Q&A texts) — embed into the HTML
    attachments = _embed_attachments(raw_attachments)
    screenshots_dir = REPORTS_DIR / "screenshots"
    if screenshots_dir.exists():
        shutil.rmtree(screenshots_dir, ignore_errors=True)

    duration = sum(
        step.get("result", {}).get("duration", 0)
        for feature in features
        for element in feature.get("elements", [])
        for step in element.get("steps", [])
    )

    data = {
        "projectName": "Playwright + Behave BDD Framework",
        "env": env.upper(),
        "build": stamp,
        "verdict": verdict,
        "stats": stats,
        "durationSeconds": round(duration, 1),
        "browser": os.environ.get("BROWSER", "chromium"),
        "platform": os.name,
        "baseUrl": os.environ.get("BASE_URL", "-"),
        "apiBaseUrl": os.environ.get("API_BASE_URL", "-"),
        "tags": os.environ.get("TAGS") or os.environ.get("RUN_ARGS") or "(all)",
        "features": features,
        "attachments": attachments,
    }

    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    html = template.replace("/*__DATA__*/null", json.dumps(data))
    report_path = run_dir / "html" / "index.html"
    report_path.write_text(html, encoding="utf-8")

    # Rerun file — failing scenario ID tags for `python scripts/run.py --rerun`
    failing_tags = sorted(
        {
            tag
            for feature in features
            for element in feature.get("elements", [])
            if _scenario_status(element) == "failed"
            for tag in element.get("tags", [])
            if tag.startswith("TC_") or tag.startswith("@TC_")
        }
    )
    (REPORTS_DIR / "rerun.txt").write_text("\n".join(failing_tags), encoding="utf-8")

    # Run history ledger
    history = _read_json(HISTORY_FILE, [])
    history.append(
        {
            "timestamp": stamp,
            "env": env,
            "browser": os.environ.get("BROWSER", "chromium"),
            "tags": os.environ.get("TAGS") or os.environ.get("RUN_ARGS") or "(all)",
            "verdict": verdict,
            **stats,
            "report": str((run_dir / "html" / "index.html").relative_to(ROOT)),
        }
    )
    HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")
    (REPORTS_DIR / "latest-run.txt").write_text(str(run_dir), encoding="utf-8")

    logger.info("=" * 70)
    logger.info(
        f"Run verdict : {verdict}  ({stats['passed']} passed, "
        f"{stats['failed']} failed, {stats['skipped']} skipped)"
    )
    logger.info(f"Report      : {report_path}")
    logger.info(f"Run history : {HISTORY_FILE} ({len(history)} runs tracked)")
    logger.info("=" * 70)
    return {"run_dir": str(run_dir), "report_path": str(report_path), "stats": stats, "verdict": verdict}
