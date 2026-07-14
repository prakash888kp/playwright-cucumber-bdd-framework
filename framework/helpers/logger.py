"""Winston-style logger — console + daily file, with scenario-scoped child loggers."""
import logging
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("framework")
if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(getattr(logging, os.environ.get("LOG_LEVEL", "info").upper(), logging.INFO))
    console.setFormatter(fmt)
    logger.addHandler(console)

    file_handler = logging.FileHandler(
        LOG_DIR / f"execution-{date.today().isoformat()}.log", encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)


class _ScenarioAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[{self.extra['label']}] {msg}", kwargs


def scenario_logger(label: str) -> logging.LoggerAdapter:
    """Child logger that prefixes every line with the scenario name."""
    return _ScenarioAdapter(logger, {"label": label})
