
import os
from pathlib import Path
from dotenv import load_dotenv

# Locate the .env file in the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE, override=True)

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()

API_FOOTBALL_BASE_URL = os.getenv(
    "API_FOOTBALL_BASE_URL",
    "https://v3.football.api-sports.io",
).strip()


def extras_enabled() -> bool:
    """Live-score / fixture-lookup routes are OFF by default: they let any visitor trigger provider
    calls. Set ENABLE_EXTRA_ENDPOINTS=1 only on a private/local server."""
    return os.getenv("ENABLE_EXTRA_ENDPOINTS", "").strip().lower() in ("1", "true", "yes")


def docs_enabled() -> bool:
    return os.getenv("ENABLE_DOCS", "").strip().lower() in ("1", "true", "yes")
