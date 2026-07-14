"""Environment loader — merges (in priority order):
  1. Real process env / CLI            (highest — shell exports win)
  2. config/env/.env.<ENV>             (environment-specific values)
  3. .env at project root              (defaults)
"""
import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parents[2]


def load_env() -> str:
    root_file = ROOT / ".env"
    root_values = dotenv_values(root_file) if root_file.exists() else {}

    env = (os.environ.get("ENV") or root_values.get("ENV") or "qa").lower()

    env_file = ROOT / "config" / "env" / f".env.{env}"
    if env_file.exists():
        load_dotenv(env_file, override=False)  # shell still wins
    if root_file.exists():
        load_dotenv(root_file, override=False)  # fills remaining defaults

    os.environ["ENV"] = env
    return env
