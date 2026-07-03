"""Loads environment variables and YAML config into one place other modules import from."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool_env(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _load_yaml(path: Path) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_NAME = os.getenv("SENDER_NAME", "AI Weekly Digest")

MAINTAINER_EMAIL = os.getenv("MAINTAINER_EMAIL", "")

DRY_RUN = _bool_env("DRY_RUN", False)

# Single accent color used throughout the email template — swap here to rebrand.
ACCENT_COLOR = "#5B47FB"

SOURCES_PATH = BASE_DIR / "config" / "sources.yaml"
RECIPIENTS_PATH = BASE_DIR / "config" / "recipients.yaml"
SENT_HISTORY_PATH = BASE_DIR / "data" / "sent_history.json"
LAST_DIGEST_PATH = BASE_DIR / "data" / "last_digest.json"
LOGS_DIR = BASE_DIR / "logs"
TEMPLATES_DIR = BASE_DIR / "templates"


def load_sources() -> list[dict]:
    return _load_yaml(SOURCES_PATH).get("sources", [])


def load_recipients() -> list[str]:
    return _load_yaml(RECIPIENTS_PATH).get("recipients", [])
