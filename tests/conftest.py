"""pytest-bdd wiring — fixtures + hooks replacing behave's environment.py.

Per xdist worker: one Playwright + one browser (session fixtures are
per-process). Per scenario: a `context` namespace (behave-style), with a
browser context/page only for @ui scenarios. Per step: timing, result
records, and screenshots. Each worker writes reports/results.<worker>.json
and attachments.<worker>.json; the report builder merges them.
"""
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.config.env_loader import load_env  # noqa: E402

load_env()

from playwright.sync_api import sync_playwright  # noqa: E402

from framework.helpers.api_helper import ApiHelper  # noqa: E402
from framework.helpers.bedrock_helper import BedrockHelper  # noqa: E402
from framework.helpers.logger import logger, scenario_logger  # noqa: E402
from framework.support.page_manager import PageManager  # noqa: E402

pytest_plugins = [
    "tests.steps.ui_steps",
    "tests.steps.api_steps",
    "tests.steps.rag_steps",
]

REPORTS_DIR = ROOT / "reports"
TRACE_DIR = REPORTS_DIR / "traces"
VIDEO_DIR = REPORTS_DIR / "videos"
SCREENSHOT_DIR = REPORTS_DIR / "screenshots"

BROWSERS = ("chromium", "firefox", "webkit")

_records: list[dict] = []  # finished scenario records (this worker)
_attachments: dict[str, list] = {}  # scenario location -> attachments


def _worker_id() -> str:
    return os.environ.get("PYTEST_XDIST_WORKER", "main")


def _slug(text: str) -> str:
    return re.sub(r"\W+", "_", text)


def _step_keyword(step) -> str:
    return getattr(step, "keyword", None) or step.type.capitalize()


# ---------------------------------------------------------------- fixtures

@pytest.fixture(scope="session")
def pw():
    p = sync_playwright().start()
    yield p
    p.stop()


@pytest.fixture(scope="session")
def browser(pw):
    name = os.environ.get("BROWSER", "chromium").lower()
    if name not in BROWSERS:
        raise ValueError(f'Unknown BROWSER "{name}". Use chromium | firefox | webkit')
    headless = os.environ.get("HEADLESS", "true").lower() != "false"
    b = getattr(pw, name).launch(headless=headless)
    logger.info(f"[{_worker_id()}] Launched {name} (headless={headless}) | ENV={os.environ.get('ENV')}")
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    yield b
    b.close()


@pytest.fixture
def context(request, pw, browser):
    """behave-style scenario context: data, log, api/bedrock helpers, and a
    browser page + PageManager for @ui scenarios."""
    tags = {m.name for m in request.node.iter_markers()}
    name = request.node._bdd["name"] if hasattr(request.node, "_bdd") else request.node.name

    ctx = SimpleNamespace(
        log=scenario_logger(name),
        data={},
        rag={},
        api=ApiHelper(pw),
        bedrock=BedrockHelper(),
        is_ui_scenario="ui" in tags,
        browser_context=None,
        page=None,
        pages=None,
        attachments=_attachments.setdefault(getattr(request.node, "_scenario_key", name), []),
    )
    ctx.log.info(f"--- Scenario started: {name} ---")

    if ctx.is_ui_scenario:
        kwargs = {"viewport": {"width": 1440, "height": 900}}
        if os.environ.get("VIDEO") == "on":
            kwargs["record_video_dir"] = str(VIDEO_DIR)
        ctx.browser_context = browser.new_context(**kwargs)
        if os.environ.get("TRACE", "on-failure") != "off":
            ctx.browser_context.tracing.start(screenshots=True, snapshots=True)
        ctx.page = ctx.browser_context.new_page()
        ctx.page.set_default_timeout(int(os.environ.get("DEFAULT_TIMEOUT", 30000)))
        ctx.pages = PageManager(ctx.page, ctx.log)

    request.node._ctx = ctx
    yield ctx

    rep = getattr(request.node, "rep_call", None)
    failed = bool(rep and rep.failed)

    if ctx.page and failed:
        try:
            shot_dir = SCREENSHOT_DIR / _slug(request.node._scenario_key)
            shot_dir.mkdir(parents=True, exist_ok=True)
            path = shot_dir / "failure.png"
            ctx.page.screenshot(path=str(path), full_page=True)
            ctx.attachments.append(
                {"type": "image/png", "name": "Failure screenshot", "path": str(path.relative_to(REPORTS_DIR))}
            )
        except Exception:
            pass

    if ctx.browser_context:
        trace_mode = os.environ.get("TRACE", "on-failure")
        if trace_mode != "off":
            keep = failed or trace_mode == "on"
            trace_path = TRACE_DIR / f"{_slug(name)}.zip"
            try:
                ctx.browser_context.tracing.stop(path=str(trace_path) if keep else None)
                if keep:
                    ctx.log.info(f"Trace saved: {trace_path}")
            except Exception:
                pass
        ctx.browser_context.close()

    ctx.api.dispose()
    status = "FAILED" if failed else "PASSED" if rep and rep.passed else "SKIPPED"
    ctx.log.info(f"--- Scenario {status}: {name} ---")


# ---------------------------------------------------------------- bdd hooks

def pytest_bdd_before_scenario(request, feature, scenario):
    tags = set(scenario.tags) | set(feature.tags)  # scenario.tags alone omits feature-level tags
    feature_location = f"features/{feature.rel_filename}".replace("\\", "/")
    location = f"{feature_location}:{scenario.line_number}"
    request.node._scenario_key = location
    request.node._step_idx = 0
    request.node._bdd = {
        "feature_name": feature.name,
        "feature_location": feature_location,
        "name": scenario.name,
        "tags": sorted(tags),
        "location": location,
        "steps": [],
        "all_steps": [{"keyword": _step_keyword(s), "name": s.name} for s in scenario.steps],
        "start": time.time(),
        "worker": _worker_id(),
    }
    # Reset per attempt: pytest-rerunfailures re-enters this hook on each retry,
    # so a fresh list keeps only the final attempt's screenshots.
    _attachments[location] = []

    # Skip RAG scenarios gracefully when AWS credentials / KB are not configured,
    # so the suite stays green on machines without Bedrock access.
    if "rag" in tags and (not BedrockHelper().has_credentials() or not os.environ.get("BEDROCK_KB_ID")):
        logger.warning("Skipping RAG scenario — AWS credentials or BEDROCK_KB_ID not configured")
        pytest.skip("AWS credentials or BEDROCK_KB_ID not configured")


def pytest_bdd_before_step_call(request, feature, scenario, step, step_func, step_func_args):
    request.node._step_start = time.monotonic()


def _record_step(request, step, status, error=None):
    duration = time.monotonic() - getattr(request.node, "_step_start", time.monotonic())
    result = {"status": status, "duration": round(duration, 4)}
    if error:
        result["error_message"] = error
    request.node._bdd["steps"].append({"keyword": _step_keyword(step), "name": step.name, "result": result})


def _step_screenshot(request, step, failed=False):
    """Per-step screenshots for UI scenarios. STEP_SCREENSHOTS: on | failure | off"""
    ctx = getattr(request.node, "_ctx", None)
    mode = os.environ.get("STEP_SCREENSHOTS", "on").lower()
    if mode == "off" or not ctx or not ctx.page:
        return
    if mode == "failure" and not failed:
        return
    # A screenshot of a not-yet-navigated page (about:blank) is a blank white
    # frame — skip it unless the step actually failed there.
    if not failed:
        try:
            if not ctx.page.url or ctx.page.url == "about:blank":
                return
        except Exception:
            return
    try:
        key = request.node._scenario_key
        shot_dir = SCREENSHOT_DIR / _slug(key)
        shot_dir.mkdir(parents=True, exist_ok=True)
        path = shot_dir / f"{request.node._step_idx + 1:03d}.png"
        ctx.page.screenshot(path=str(path), animations="disabled")
        _attachments[key].append(
            {
                "type": "image/png",
                "name": step.name,
                "path": str(path.relative_to(REPORTS_DIR)),
                "step_index": request.node._step_idx,
                "status": "failed" if failed else "passed",
            }
        )
    except Exception as exc:  # never fail a scenario because of a screenshot
        logger.debug(f"Step screenshot failed: {exc}")


def pytest_bdd_after_step(request, feature, scenario, step, step_func, step_func_args):
    _record_step(request, step, "passed")
    _step_screenshot(request, step)
    request.node._step_idx += 1


def pytest_bdd_step_error(request, feature, scenario, step, step_func, step_func_args, exception):
    error = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
    _record_step(request, step, "failed", error=error)
    _step_screenshot(request, step, failed=True)
    request.node._step_idx += 1


# ---------------------------------------------------------------- reporting

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)

    if rep.when == "call" and hasattr(item, "_bdd"):
        bdd = item._bdd
        status = "passed" if rep.passed else "failed" if rep.failed else "skipped"
        for pending in bdd["all_steps"][len(bdd["steps"]):]:
            bdd["steps"].append({**pending, "result": {"status": "untested"}})
        # pytest-rerunfailures re-runs failing tests: drop any earlier attempt's
        # record for this scenario so only the final outcome is reported.
        _records[:] = [r for r in _records if r["location"] != bdd["location"]]
        _records.append(
            {
                "feature_name": bdd["feature_name"],
                "feature_location": bdd["feature_location"],
                "name": bdd["name"],
                "tags": bdd["tags"],
                "location": bdd["location"],
                "status": status,
                "steps": bdd["steps"],
                "start": bdd["start"],
                "end": time.time(),
                "worker": bdd["worker"],
            }
        )


def pytest_sessionfinish(session, exitstatus):
    REPORTS_DIR.mkdir(exist_ok=True)
    worker = _worker_id()
    (REPORTS_DIR / f"results.{worker}.json").write_text(json.dumps(_records, indent=2), encoding="utf-8")
    (REPORTS_DIR / f"attachments.{worker}.json").write_text(
        json.dumps(_attachments, indent=2), encoding="utf-8"
    )
