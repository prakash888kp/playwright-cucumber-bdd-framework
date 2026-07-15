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


def _load_worker_outputs() -> tuple[list, dict]:
    """Merge per-xdist-worker results.*.json / attachments.*.json into one
    behave-shaped features list + attachments manifest."""
    records = []
    for file in sorted(REPORTS_DIR.glob("results.*.json")):
        records.extend(_read_json(file, []))
    features: dict[str, dict] = {}
    for r in records:
        feature = features.setdefault(
            r["feature_location"],
            {"name": r["feature_name"], "location": r["feature_location"], "elements": []},
        )
        feature["elements"].append(
            {
                "type": "scenario",
                "name": r["name"],
                "tags": r["tags"],
                "location": r["location"],
                "status": r["status"],
                "steps": r["steps"],
                "start": r.get("start"),
                "end": r.get("end"),
                "worker": r.get("worker"),
            }
        )
    attachments: dict[str, list] = {}
    for file in sorted(REPORTS_DIR.glob("attachments.*.json")):
        for key, items in _read_json(file, {}).items():
            attachments.setdefault(key, []).extend(items)
    return list(features.values()), attachments


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
    features, raw_attachments = _load_worker_outputs()
    if not features:
        logger.error("No reports/results.*.json found — nothing to report.")
        return None

    stats = read_run_stats(features)
    verdict = "FAILED" if stats["failed"] > 0 else "PASSED"
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    env = os.environ.get("ENV", "qa")
    run_dir = REPORTS_DIR / f"run_{stamp}_{env}_{verdict}"
    (run_dir / "html").mkdir(parents=True, exist_ok=True)

    # Archive this run's raw artifacts
    (run_dir / "results.json").write_text(json.dumps(features, indent=2), encoding="utf-8")
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

    # This run's history entry — appended to the ledger AND embedded in the
    # report (with the recent past) so the trend chart includes this run.
    history = _read_json(HISTORY_FILE, [])
    history_entry = {
        "timestamp": stamp,
        "env": env,
        "browser": os.environ.get("BROWSER", "chromium"),
        "tags": os.environ.get("TAGS") or os.environ.get("RUN_ARGS") or "(all)",
        "verdict": verdict,
        **stats,
        "report": str((run_dir / "html" / "index.html").relative_to(ROOT)),
    }

    data = {
        "projectName": "Playwright + pytest-bdd Framework",
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
        "history": [
            {k: h.get(k) for k in ("timestamp", "verdict", "scenarios", "passed", "failed", "skipped")}
            for h in [*history, history_entry][-20:]
        ],
    }

    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    html = template.replace("/*__DATA__*/null", json.dumps(data))
    report_path = run_dir / "html" / "index.html"
    report_path.write_text(html, encoding="utf-8")

    # Rerun file — failing scenario ID tags for `python scripts/run.py --rerun`
    failing_tags = sorted(
        {
            tag.lstrip("@")
            for feature in features
            for element in feature.get("elements", [])
            if _scenario_status(element) == "failed"
            for tag in element.get("tags", [])
            if tag.lstrip("@").startswith("TC_")
        }
    )
    (REPORTS_DIR / "rerun.txt").write_text("\n".join(failing_tags), encoding="utf-8")

    # Run history ledger
    history.append(history_entry)
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
