"""behave hooks — browser per run, fresh context+page per @ui scenario,
tracing/video per env flags, per-step screenshots, attachments manifest
for the HTML report, graceful RAG skip without AWS credentials.
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.config.env_loader import load_env  # noqa: E402

load_env()

from playwright.sync_api import sync_playwright  # noqa: E402

from framework.helpers.api_helper import ApiHelper  # noqa: E402
from framework.helpers.bedrock_helper import BedrockHelper  # noqa: E402
from framework.helpers.logger import logger, scenario_logger  # noqa: E402
from framework.support.page_manager import PageManager  # noqa: E402

REPORTS_DIR = ROOT / "reports"
TRACE_DIR = REPORTS_DIR / "traces"
VIDEO_DIR = REPORTS_DIR / "videos"
SCREENSHOT_DIR = REPORTS_DIR / "screenshots"
ATTACHMENTS_FILE = REPORTS_DIR / "attachments.json"

BROWSERS = ("chromium", "firefox", "webkit")


def _slug(text: str) -> str:
    return re.sub(r"\W+", "_", text)


def before_all(context):
    name = os.environ.get("BROWSER", "chromium").lower()
    if name not in BROWSERS:
        raise ValueError(f'Unknown BROWSER "{name}". Use chromium | firefox | webkit')
    context.playwright = sync_playwright().start()
    headless = os.environ.get("HEADLESS", "true").lower() != "false"
    context.browser = getattr(context.playwright, name).launch(headless=headless)
    logger.info(f"Launched {name} (headless={headless}) | ENV={os.environ.get('ENV')}")

    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    context.attachments = {}  # scenario location -> list of attachments for the report


def before_feature(context, feature):
    # RETRY env: re-run failing scenarios up to N extra times (flake shield).
    retries = int(os.environ.get("RETRY", 0))
    if retries > 0:
        from behave.contrib.scenario_autoretry import patch_scenario_with_autoretry

        for scenario in feature.scenarios:
            patch_scenario_with_autoretry(scenario, max_attempts=retries + 1)


def before_scenario(context, scenario):
    context.log = scenario_logger(scenario.name)
    context.log.info(f"--- Scenario started: {scenario.name} ---")

    tags = scenario.effective_tags
    context.is_ui_scenario = "ui" in tags
    context.data = {}
    context.rag = {}
    context.api = ApiHelper(context.playwright)
    context.bedrock = BedrockHelper()
    context.step_index = 0
    context.scenario_key = f"{scenario.filename}:{scenario.line}".replace("\\", "/")
    context.attachments[context.scenario_key] = []

    # Skip RAG scenarios gracefully when AWS credentials / KB are not configured,
    # so the suite stays green on machines without Bedrock access.
    if "rag" in tags and (not context.bedrock.has_credentials() or not os.environ.get("BEDROCK_KB_ID")):
        logger.warning("Skipping RAG scenario — AWS credentials or BEDROCK_KB_ID not configured")
        scenario.skip("AWS credentials or BEDROCK_KB_ID not configured")
        return

    # Browser context only for UI scenarios — API/RAG runs stay lightweight
    if context.is_ui_scenario:
        kwargs = {"viewport": {"width": 1440, "height": 900}}
        if os.environ.get("VIDEO") == "on":
            kwargs["record_video_dir"] = str(VIDEO_DIR)
        context.browser_context = context.browser.new_context(**kwargs)
        if os.environ.get("TRACE", "on-failure") != "off":
            context.browser_context.tracing.start(screenshots=True, snapshots=True)
        context.page = context.browser_context.new_page()
        context.page.set_default_timeout(int(os.environ.get("DEFAULT_TIMEOUT", 30000)))
        context.pages = PageManager(context.page, context.log)
    else:
        context.browser_context = None
        context.page = None


def after_step(context, step):
    """Per-step screenshots for UI scenarios so the report shows visual evidence
    of every action/validation. STEP_SCREENSHOTS: on (default) | failure | off
    """
    context.step_index += 1
    mode = os.environ.get("STEP_SCREENSHOTS", "on").lower()
    if mode == "off" or not getattr(context, "page", None):
        return
    if mode == "failure" and step.status.name != "failed":
        return
    try:
        shot_dir = SCREENSHOT_DIR / _slug(context.scenario_key)
        shot_dir.mkdir(parents=True, exist_ok=True)
        path = shot_dir / f"{context.step_index:03d}.png"
        context.page.screenshot(path=str(path), animations="disabled")
        context.attachments[context.scenario_key].append(
            {
                "type": "image/png",
                "name": step.name,
                "path": str(path.relative_to(REPORTS_DIR)),
                "step_index": context.step_index - 1,
                "status": step.status.name,
            }
        )
    except Exception as exc:  # never fail a scenario because of a screenshot
        logger.debug(f"Step screenshot failed: {exc}")


def after_scenario(context, scenario):
    failed = scenario.status.name == "failed"

    if getattr(context, "page", None) and failed:
        try:
            shot_dir = SCREENSHOT_DIR / _slug(context.scenario_key)
            shot_dir.mkdir(parents=True, exist_ok=True)
            path = shot_dir / "failure.png"
            context.page.screenshot(path=str(path), full_page=True)
            context.attachments[context.scenario_key].append(
                {"type": "image/png", "name": "Failure screenshot", "path": str(path.relative_to(REPORTS_DIR))}
            )
        except Exception:
            pass

    if getattr(context, "browser_context", None):
        trace_mode = os.environ.get("TRACE", "on-failure")
        if trace_mode != "off":
            keep_trace = failed or trace_mode == "on"
            trace_path = TRACE_DIR / f"{_slug(scenario.name)}.zip"
            try:
                context.browser_context.tracing.stop(path=str(trace_path) if keep_trace else None)
                if keep_trace:
                    context.log.info(f"Trace saved: {trace_path}")
            except Exception:
                pass
        context.browser_context.close()

    context.api.dispose()
    getattr(context, "log", logger).info(
        f"--- Scenario {scenario.status.name.upper()}: {scenario.name} ---"
    )


def after_all(context):
    if getattr(context, "browser", None):
        context.browser.close()
    if getattr(context, "playwright", None):
        context.playwright.stop()
    # Manifest consumed by framework/helpers/report_builder.py
    ATTACHMENTS_FILE.write_text(json.dumps(context.attachments, indent=2), encoding="utf-8")
