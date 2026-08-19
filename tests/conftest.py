"""Global test isolation from optional external telemetry."""
from __future__ import annotations

import os


# A developer's local .env may contain valid tracing credentials. Unit and
# benchmark tests must never export traces or start background network retries.
os.environ["LANGFUSE_TRACING_ENABLED"] = "false"
