#!/usr/bin/env python3
"""
Volcengine Seedream image generation backend.

Configuration keys:
  AGENT_API_KEY                                    (required)
  ARK_AGENT_PLAN_BASE_URL                          (optional)
  PPT_IMAGE_MODEL                                  (optional; Seedream 5.0 Lite)
  VOLCENGINE_OUTPUT_FORMAT                         (optional; png or jpeg)
"""

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from console_encoding import configure_utf8_stdio  # noqa: E402

configure_utf8_stdio()

if __name__ == "__main__":
    print(__doc__)
    print("Use via: python3 skills/ppt-master/scripts/image_gen.py \"prompt\" --backend volcengine")
    raise SystemExit(0 if any(arg in {"-h", "--help", "help"} for arg in sys.argv[1:]) else 1)

import os
import time

import requests

from image_backends.backend_common import (
    MAX_RETRIES,
    download_image,
    http_error,
    is_permanent_error,
    is_rate_limit_error,
    normalize_image_size,
    require_api_key,
    resolve_output_path,
    retry_delay,
)


DEFAULT_ENDPOINT = "https://ark.cn-beijing.volces.com/api/plan/v3/images/generations"
DEFAULT_MODEL = "doubao-seedream-5.0-lite"
DEFAULT_IMAGE_SIZE = "2K"
SUPPORTED_MODELS = {
    DEFAULT_MODEL,
    # Versioned public Model ID accepted by standard Ark deployments.
    "doubao-seedream-5-0-260128",
}
SUPPORTED_IMAGE_SIZES = {"1K", "2K", "4K"}


def _validate_model(model: str) -> str:
    """Limit the backend to the Agent Plan Seedream 5.0 Lite contract."""
    resolved = model.strip()
    if resolved not in SUPPORTED_MODELS:
        raise ValueError(
            f"Unsupported Volcengine model '{model}'. Supported: {sorted(SUPPORTED_MODELS)}"
        )
    return resolved


def _resolve_url(base_url: str) -> str:
    """Resolve the Agent Plan Ark image-generation endpoint."""
    base = base_url.rstrip("/")
    if base.endswith("/images/generations"):
        return base
    if base.endswith(("/api/v3", "/api/plan/v3")):
        return base + "/images/generations"
    return base + "/images/generations"


def _resolve_size(aspect_ratio: str, image_size: str) -> str:
    """Validate an Ark logical size preset; ratio remains prompt-level guidance."""
    normalized = normalize_image_size(image_size)
    if normalized not in SUPPORTED_IMAGE_SIZES:
        supported_sizes = ", ".join(sorted(SUPPORTED_IMAGE_SIZES))
        raise ValueError(
            f"Unsupported image size '{image_size}' for Volcengine backend. "
            f"Seedream 5.0 Lite supports these presets: {supported_sizes}."
        )
    if not aspect_ratio or ":" not in aspect_ratio:
        raise ValueError(f"Invalid aspect ratio: {aspect_ratio!r}")
    return normalized


def _output_format() -> str:
    value = os.environ.get("VOLCENGINE_OUTPUT_FORMAT", "png").strip().lower()
    if value not in {"png", "jpeg"}:
        raise ValueError("VOLCENGINE_OUTPUT_FORMAT must be png or jpeg")
    return value


def _generate_image(api_key: str, prompt: str,
                    aspect_ratio: str = "1:1", image_size: str = DEFAULT_IMAGE_SIZE,
                    output_dir: str = None, filename: str = None,
                    model: str = DEFAULT_MODEL, base_url: str = DEFAULT_ENDPOINT) -> str:
    """Generate one image with the Volcengine backend."""
    model = _validate_model(model)
    size = _resolve_size(aspect_ratio, image_size)
    url = _resolve_url(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    output_format = _output_format()
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "output_format": output_format,
        "response_format": "url",
        "watermark": False,
        # PPT Master requests one image per manifest item. Do not let a prompt
        # accidentally turn into a charged multi-image sequence.
        "sequential_image_generation": "disabled",
    }

    print("[Volcengine Seedream]")
    print(f"  Model:        {model}")
    print(f"  Prompt:       {prompt[:120]}{'...' if len(prompt) > 120 else ''}")
    print(f"  Aspect Ratio: {aspect_ratio} (prompt guidance)")
    print(f"  Size:         {size}")
    print()
    print("  [..] Generating...", end="", flush=True)
    start = time.time()
    response = requests.post(url, headers=headers, json=payload, timeout=300)
    elapsed = time.time() - start
    print(f"\n  [DONE] Response received ({elapsed:.1f}s)")

    if response.status_code != 200:
        raise http_error(response, "Volcengine image generation")

    data = response.json()
    items = data.get("data") or []
    image_url = items[0].get("url") if items else None
    if not image_url:
        raise RuntimeError(f"Volcengine response missing image URL: {data}")

    path = resolve_output_path(prompt, output_dir, filename, f".{output_format}")
    return download_image(image_url, path)


def generate(prompt: str,
             aspect_ratio: str = "1:1", image_size: str = DEFAULT_IMAGE_SIZE,
             output_dir: str = None, filename: str = None,
             model: str = None, max_retries: int = MAX_RETRIES) -> str:
    """Generate an image with retries using the Volcengine backend."""
    # VOLCENGINE_MODEL is reserved for the optional text-LLM provider; do not
    # let it accidentally select a text model for PPT image generation.
    resolved_model = model or os.environ.get("PPT_IMAGE_MODEL") or DEFAULT_MODEL
    _validate_model(resolved_model)
    normalized_size = normalize_image_size(image_size)
    _resolve_size(aspect_ratio, normalized_size)
    api_key = require_api_key(
        "AGENT_API_KEY",
        message=(
            "No AGENT_API_KEY found. This QuanAgent integration uses the "
            "dedicated Agent Plan credential for Volcengine Seedream only."
        ),
    )
    base_url = (
        os.environ.get("ARK_AGENT_PLAN_BASE_URL")
        or os.environ.get("VOLCENGINE_BASE_URL")
        or DEFAULT_ENDPOINT
    )

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return _generate_image(
                api_key=api_key,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                image_size=normalized_size,
                output_dir=output_dir,
                filename=filename,
                model=resolved_model,
                base_url=base_url,
            )
        except Exception as exc:
            last_error = exc
            if is_permanent_error(exc):
                raise
            if attempt >= max_retries:
                break
            limited = is_rate_limit_error(exc)
            delay = retry_delay(attempt, rate_limited=limited)
            label = "Rate limit hit" if limited else f"Error: {exc}"
            print(f"\n  [WARN] {label}. Retrying in {delay}s...")
            time.sleep(delay)

    raise RuntimeError(f"Failed after {max_retries + 1} attempts. Last error: {last_error}")
