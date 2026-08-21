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

AGENT_RECURSION_LIMIT = int(os.getenv("AGENT_RECURSION_LIMIT", "120"))
AGENT_RUN_DEADLINE_SECONDS = float(os.getenv("AGENT_RUN_DEADLINE_SECONDS", "3600"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
WEB_RESEARCH_DEADLINE_SECONDS = float(os.getenv("WEB_RESEARCH_DEADLINE_SECONDS", "55"))
WEB_RESEARCH_MAX_WORKERS = int(os.getenv("WEB_RESEARCH_MAX_WORKERS", "4"))
WEB_RESEARCH_MAX_QUERIES = int(os.getenv("WEB_RESEARCH_MAX_QUERIES", "6"))
SEARCH_PROVIDER_CONCURRENCY = int(os.getenv("WEB_SEARCH_PROVIDER_CONCURRENCY", "3"))
SEARCH_PROVIDER_TIMEOUT_SECONDS = float(os.getenv("WEB_SEARCH_PROVIDER_TIMEOUT_SECONDS", "5"))
WEB_RESEARCH_LLM_TIMEOUT = float(os.getenv("WEB_RESEARCH_LLM_TIMEOUT", "15"))
WEB_RESEARCH_LLM_MAX_RETRIES = int(os.getenv("WEB_RESEARCH_LLM_MAX_RETRIES", "1"))

# PPT visual review is deliberately independent from the primary chat model.
PPT_VISION_MODEL = os.getenv("PPT_VISION_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct").strip()
PPT_VISION_TIMEOUT = float(os.getenv("PPT_VISION_TIMEOUT", "120"))
PPT_VISION_MAX_TOKENS = int(os.getenv("PPT_VISION_MAX_TOKENS", "2000"))
# The Fast PPT lane is deliberately bounded and independent from the general
# agent deadline.  It never creates a DeepAgents subgraph or checkpoint.
PPT_FAST_DEADLINE_SECONDS = float(os.getenv("PPT_FAST_DEADLINE_SECONDS", "300"))
PPT_PAGE_CONCURRENCY = int(os.getenv("PPT_PAGE_CONCURRENCY", "4"))
PPT_PAGE_TIMEOUT_SECONDS = float(os.getenv("PPT_PAGE_TIMEOUT_SECONDS", "100"))
PPT_IMAGE_LIMIT = int(os.getenv("PPT_IMAGE_LIMIT", "3"))
PPT_IMAGE_CONCURRENCY = int(os.getenv("PPT_IMAGE_CONCURRENCY", "3"))
PPT_FAST_VISION_TIMEOUT = float(os.getenv("PPT_FAST_VISION_TIMEOUT", "35"))

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

MOSS_ENDPOINT = os.getenv("MOSS_ENDPOINT", "https://moss.lesso.com").rstrip("/")
MOSS_REGION = os.getenv("MOSS_REGION", "fs").strip() or "fs"
MOSS_BUCKET = (os.getenv("MOSS_BUCKET") or os.getenv("MOSS_UPLOAD_BUCKET") or "").strip()
MOSS_ACCESS_KEY = os.getenv("MOSS_ACCESS_KEY", "").strip()
MOSS_SECRET_KEY = os.getenv("MOSS_SECRET_KEY", "").strip()
MOSS_KEY_PREFIX = os.getenv("MOSS_KEY_PREFIX", "quan").strip().strip("/") or "quan"


def ensure_runtime_dirs() -> None:
    """Create only active runtime directories; archived data is read-only."""
    for directory in (TMP_DIR, OUTPUT_DIR, STATE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
