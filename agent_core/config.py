"""Runtime configuration shared by the entrypoints."""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(os.getenv("WORKSPACE_ROOT", "workspace"))
OUTPUT_DIR = WORKSPACE_ROOT / "output"
TMP_DIR = WORKSPACE_ROOT / "tmp"
SKILLS_DIR = WORKSPACE_ROOT / "skills"
UPLOADS_DIR = WORKSPACE_ROOT / "uploads"
STATE_DIR = WORKSPACE_ROOT / "state"
CHECKPOINT_DB_PATH = STATE_DIR / "checkpoints.sqlite"

AGENT_RECURSION_LIMIT = int(os.getenv("AGENT_RECURSION_LIMIT", "40"))
AGENT_RUN_DEADLINE_SECONDS = float(os.getenv("AGENT_RUN_DEADLINE_SECONDS", "300"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))

HITL_ENABLED_DEFAULT = os.getenv("HITL_ENABLED", "true").lower() in {"1", "true", "yes"}
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(20 * 1024 * 1024)))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


def langfuse_is_configured(environ: Mapping[str, str] | None = None) -> bool:
    values = os.environ if environ is None else environ
    enabled = str(values.get("LANGFUSE_TRACING_ENABLED", "true")).strip().lower()
    return enabled in {"1", "true", "yes", "on"} and bool(
        str(values.get("LANGFUSE_PUBLIC_KEY", "")).strip()
        and str(values.get("LANGFUSE_SECRET_KEY", "")).strip()
    )


LANGFUSE_ENABLED = langfuse_is_configured()

AGENT_MODE_DEFAULT = os.getenv("AGENT_MODE", "agent").strip().lower()
if AGENT_MODE_DEFAULT not in {"agent", "plan"}:
    AGENT_MODE_DEFAULT = "agent"
EXECUTE_PROFILE_DEFAULT = os.getenv("EXECUTE_PROFILE", "workspace_auto").strip().lower()
if EXECUTE_PROFILE_DEFAULT not in {"workspace_auto", "manual", "ask_all", "legacy"}:
    EXECUTE_PROFILE_DEFAULT = "workspace_auto"
CHANNEL_DENY_EXECUTE = os.getenv("CHANNEL_DENY_EXECUTE", "true").lower() in {"1", "true", "yes"}
HOOKS_DIR = Path(os.getenv("HOOKS_DIR", str(WORKSPACE_ROOT / "hooks")))

AGENT_API_TOKEN = os.getenv("AGENT_API_TOKEN", "").strip()
_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",") if o.strip()]
WEB_HOST_DEFAULT = "127.0.0.1"

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SEARCH_PROVIDER_COOLDOWN_SECONDS = int(os.getenv("SEARCH_PROVIDER_COOLDOWN_SECONDS", "3600"))


def ensure_runtime_dirs() -> None:
    """Create only active runtime directories; archived data is read-only."""
    for directory in (TMP_DIR, OUTPUT_DIR, STATE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
