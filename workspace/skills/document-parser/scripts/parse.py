#!/usr/bin/env python3
"""Parse documents to Markdown using MinerU API with fallback strategy.

Part of the document-parser skill. Invoked by the agent via the `execute` tool:

    python skills/document-parser/scripts/parse.py \
        --url https://example.com/doc.pdf \
        --out output/document.md

Fallback strategy:
1. Try 🎯 Precision Extract API (vlm model, high accuracy) first
2. On failure, fall back to ⚡ Agent Lightweight Extract API (no token)
3. If both fail, report error
"""
from __future__ import annotations

import argparse
import io
import sys
import time
import zipfile
from pathlib import Path
from typing import Optional

import httpx

MINERU_TOKEN = "eyJ0eXBlIjoiSldUIiwiYWxnIjoiSFM1MTIifQ.eyJqdGkiOiI3NDkwMDU0NiIsInJvbCI6IlJPTEVfUkVHSVNURVIiLCJpc3MiOiJPcGVuWExhYiIsImlhdCI6MTc3OTA2ODc4MCwiY2xpZW50SWQiOiJsa3pkeDU3bnZ5MjJqa3BxOXgydyIsInBob25lIjoiMTM2NzA2NTYxMTciLCJvcGVuSWQiOm51bGwsInV1aWQiOiIyM2FhYzFiMi1kZjU2LTQ3NDctOWRkZS1lOTY4M2JlMzY1OTUiLCJlbWFpbCI6IiIsImV4cCI6MTc4Njg0NDc4MH0.bo4leyOlFlEJ8kCgSicyL1D_sbp99Fryroen9Xgr-SRskv4aiEV-OlFQLWLfqru08Myv9k8FmLuvnadFAbjzJQ"

PRECISION_BASE_URL = "https://mineru.net/api/v4"
AGENT_BASE_URL = "https://mineru.net/api/v1/agent"

STATE_LABELS = {
    "pending": "排队中",
    "running": "解析中",
    "done": "完成",
    "failed": "失败",
    "converting": "格式转换中",
    "waiting-file": "等待文件上传",
    "uploading": "文件下载中",
}


def _resolve_out_path(out_arg: str) -> Path:
    p = Path(out_arg)
    if p.is_absolute():
        return p
    if out_arg.startswith("/"):
        return Path(out_arg.lstrip("/"))
    return p


def _bool_arg(val: str) -> bool:
    if isinstance(val, bool):
        return val
    return val.lower() in ("true", "1", "yes", "y")


def precision_parse_url(
    client: httpx.Client,
    url: str,
    model_version: str,
    language: str,
    enable_table: bool,
    enable_formula: bool,
    is_ocr: bool,
    page_range: Optional[str],
) -> Optional[str]:
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MINERU_TOKEN}",
        }
        data = {
            "url": url,
            "model_version": model_version,
            "language": language,
            "enable_table": enable_table,
            "enable_formula": enable_formula,
            "is_ocr": is_ocr,
        }
        is_html = url.lower().endswith(".html") or url.lower().endswith(".htm")
        if is_html:
            data["model_version"] = "MinerU-HTML"
        if page_range:
            data["page_ranges"] = page_range

        resp = client.post(f"{PRECISION_BASE_URL}/extract/task", headers=headers, json=data, timeout=30)
        if resp.status_code != 200:
            print(f"[Precision API] HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            return None
        result = resp.json()
        if result.get("code") != 0:
            print(f"[Precision API] Error: {result.get('msg', 'Unknown error')}", file=sys.stderr)
            return None
        task_id = result["data"]["task_id"]
        print(f"[Precision API] Task submitted: {task_id}")
        return task_id
    except Exception as e:
        print(f"[Precision API] Request failed: {e}", file=sys.stderr)
        return None


def precision_upload_and_get_task(
    client: httpx.Client,
    file_path: Path,
    model_version: str,
    language: str,
    enable_table: bool,
    enable_formula: bool,
    is_ocr: bool,
    page_range: Optional[str],
    poll_interval: int,
    timeout: int,
) -> Optional[str]:
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MINERU_TOKEN}",
        }
        file_name = file_path.name
        is_html = file_name.lower().endswith((".html", ".htm"))
        if is_html:
            model_version = "MinerU-HTML"

        data = {
            "files": [{"name": file_name}],
            "model_version": model_version,
            "language": language,
            "enable_table": enable_table,
            "enable_formula": enable_formula,
            "is_ocr": is_ocr,
        }
        if page_range:
            data["page_ranges"] = page_range

        resp = client.post(f"{PRECISION_BASE_URL}/file-urls/batch", headers=headers, json=data, timeout=30)
        if resp.status_code != 200:
            print(f"[Precision API] HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            return None
        result = resp.json()
        if result.get("code") != 0:
            print(f"[Precision API] Error: {result.get('msg', 'Unknown error')}", file=sys.stderr)
            return None

        file_url = result["data"]["file_urls"][0]
        batch_id = result["data"]["batch_id"]
        print(f"[Precision API] Got upload URL, batch_id: {batch_id}")

        with open(file_path, "rb") as f:
            file_content = f.read()
        upload_resp = client.put(file_url, content=file_content, timeout=120)
        if upload_resp.status_code not in (200, 201):
            print(f"[Precision API] Upload failed: HTTP {upload_resp.status_code}", file=sys.stderr)
            return None
        print("[Precision API] File uploaded, waiting for task creation...")

        start = time.time()
        while time.time() - start < min(30, timeout):
            time.sleep(poll_interval)
            elapsed = int(time.time() - start)
            try:
                batch_resp = client.get(
                    f"{PRECISION_BASE_URL}/extract-results/batch/{batch_id}",
                    headers=headers,
                    timeout=30,
                )
                if batch_resp.status_code != 200:
                    print(f"[{elapsed}s] Waiting for task... (HTTP {batch_resp.status_code})")
                    continue
                batch_result = batch_resp.json()
                if batch_result.get("code") != 0:
                    print(f"[{elapsed}s] Waiting for task... ({batch_result.get('msg', '')})")
                    continue
                extract_results = batch_result.get("data", {}).get("extract_result", [])
                if extract_results and len(extract_results) > 0:
                    first_result = extract_results[0]
                    task_id = first_result.get("task_id")
                    state = first_result.get("state", "")
                    if task_id and state not in ("", "waiting-file"):
                        print(f"[Precision API] Task created: {task_id} (state: {state})")
                        return task_id
                print(f"[{elapsed}s] Waiting for task creation...")
            except Exception as e:
                print(f"[{elapsed}s] Poll error: {e}, retrying...", file=sys.stderr)
        print("[Precision API] Timeout waiting for task creation after upload", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[Precision API] Upload failed: {e}", file=sys.stderr)
        return None


def precision_poll_task(
    client: httpx.Client,
    task_id: str,
    poll_interval: int,
    timeout: int,
) -> Optional[str]:
    headers = {"Authorization": f"Bearer {MINERU_TOKEN}"}
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = client.get(f"{PRECISION_BASE_URL}/extract/task/{task_id}", headers=headers, timeout=30)
            if resp.status_code != 200:
                elapsed = int(time.time() - start)
                print(f"[{elapsed}s] HTTP {resp.status_code}, retrying...", file=sys.stderr)
                time.sleep(poll_interval)
                continue
            result = resp.json()
            if result.get("code") != 0:
                print(f"[Precision API] Poll error: {result.get('msg')}", file=sys.stderr)
                return None
            data = result["data"]
            state = data.get("state", "")
            elapsed = int(time.time() - start)
            if state == "done":
                zip_url = data.get("full_zip_url", "")
                print(f"[{elapsed}s] Parse complete, downloading result...")
                return zip_url
            if state == "failed":
                err_msg = data.get("err_msg", "Unknown error")
                print(f"[{elapsed}s] Parse failed: {err_msg}", file=sys.stderr)
                return None
            label = STATE_LABELS.get(state, state)
            progress = data.get("extract_progress", {})
            if progress and state == "running":
                extracted = progress.get("extracted_pages", "?")
                total = progress.get("total_pages", "?")
                print(f"[{elapsed}s] {label}... ({extracted}/{total} pages)")
            else:
                print(f"[{elapsed}s] {label}...")
        except Exception as e:
            elapsed = int(time.time() - start)
            print(f"[{elapsed}s] Poll error: {e}, retrying...", file=sys.stderr)
        time.sleep(poll_interval)
    print(f"[Precision API] Timeout after {timeout}s", file=sys.stderr)
    return None


def _compute_url_prefix(out_path: Path) -> str:
    """计算输出目录对应的 Web URL 前缀。

    out_path 形如 output/doc.md 或 output/sub/doc.md（相对于 workspace）。
    返回形如 /output 或 /output/sub 的前缀，用于拼接图片 URL。
    """
    try:
        out_dir = out_path.parent
        cwd = Path.cwd().resolve()
        abs_out_dir = out_dir.resolve()
        rel = abs_out_dir.relative_to(cwd)
        return "/" + rel.as_posix()
    except Exception:
        return "/" + out_path.parent.as_posix()


def _rewrite_image_urls(md_content: str, url_prefix: str, extracted_rel_paths: list[str]) -> str:
    """将 Markdown 中的相对图片路径重写为 /output/... 绝对 URL。

    - 已经是 http://、https://、/ 开头的绝对路径，保持不变
    - 相对路径（如 images/xxx.jpg、./images/xxx.jpg）加上 url_prefix
    - 只有确实被提取的图片才重写，避免误改其他链接
    """
    import re

    extracted_set = set(extracted_rel_paths)
    if not extracted_set:
        return md_content

    pattern = re.compile(r'(!\[[^\]]*\]\()([^)]+)(\))')

    def _replace(m: re.Match) -> str:
        prefix, path, suffix = m.group(1), m.group(2).strip(), m.group(3)
        if path.startswith(("http://", "https://", "data:", "/")):
            return m.group(0)
        clean = path
        if clean.startswith("./"):
            clean = clean[2:]
        if clean.split("#")[0].split("?")[0] in extracted_set:
            full_url = url_prefix.rstrip("/") + "/" + clean
            return f"{prefix}{full_url}{suffix}"
        return m.group(0)

    return pattern.sub(_replace, md_content)


def precision_download_and_extract(client: httpx.Client, zip_url: str, out_path: Path) -> bool:
    try:
        print(f"[Precision API] Downloading ZIP...")
        resp = client.get(zip_url, timeout=120)
        if resp.status_code != 200:
            print(f"[Precision API] Download failed: HTTP {resp.status_code}", file=sys.stderr)
            return False
        zip_data = io.BytesIO(resp.content)
        out_dir = out_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        images_dir = out_dir / "images"

        md_content = None
        md_name = None
        image_count = 0
        extracted_image_rel_paths: list[str] = []

        with zipfile.ZipFile(zip_data) as zf:
            for name in zf.namelist():
                if name.endswith("full.md") or name == "full.md":
                    md_content = zf.read(name).decode("utf-8")
                    md_name = name

            if md_content is None:
                for name in zf.namelist():
                    if name.endswith(".md"):
                        md_content = zf.read(name).decode("utf-8")
                        md_name = name
                        break

            if md_content is None:
                print(f"[Precision API] No Markdown file found in ZIP. Files: {zf.namelist()[:20]}", file=sys.stderr)
                return False

            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                lower = name.lower()
                if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")):
                    filename = Path(name).name
                    if "/" in name:
                        parts = name.split("/")
                        for i, p in enumerate(parts):
                            if p.lower() in ("images", "image", "figures", "figure", "img", "imgs", "assets"):
                                rel_path = "/".join(parts[i:])
                                target_path = out_dir / rel_path
                                break
                        else:
                            rel_path = f"images/{filename}"
                            target_path = images_dir / filename
                    else:
                        rel_path = f"images/{filename}"
                        target_path = images_dir / filename
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    target_path.write_bytes(zf.read(name))
                    extracted_image_rel_paths.append(rel_path)
                    image_count += 1

        url_prefix = _compute_url_prefix(out_path)

        md_content = _rewrite_image_urls(md_content, url_prefix, extracted_image_rel_paths)

        out_path.write_text(md_content, encoding="utf-8")
        print(f"[Precision API] Saved Markdown to: {out_path}")
        print(f"  Source: {md_name}")
        print(f"  Content length: {len(md_content)} characters")
        if image_count > 0:
            print(f"  Extracted {image_count} images to: {images_dir}")
            print(f"  Image URL prefix: {url_prefix}")
        return True
    except Exception as e:
        print(f"[Precision API] Download/extract error: {e}", file=sys.stderr)
        return False


def agent_parse_url(
    client: httpx.Client,
    url: str,
    language: str,
    enable_table: bool,
    enable_formula: bool,
    is_ocr: bool,
    page_range: Optional[str],
) -> Optional[str]:
    try:
        data = {
            "url": url,
            "language": language,
            "enable_table": enable_table,
            "enable_formula": enable_formula,
            "is_ocr": is_ocr,
        }
        if page_range:
            data["page_range"] = page_range

        resp = client.post(f"{AGENT_BASE_URL}/parse/url", json=data, timeout=30)
        if resp.status_code != 200:
            print(f"[Agent API] HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            return None
        result = resp.json()
        if result.get("code") != 0:
            print(f"[Agent API] Error: {result.get('msg', 'Unknown error')}", file=sys.stderr)
            return None
        task_id = result["data"]["task_id"]
        print(f"[Agent API] Task submitted: {task_id}")
        return task_id
    except Exception as e:
        print(f"[Agent API] Request failed: {e}", file=sys.stderr)
        return None


def agent_upload_file(
    client: httpx.Client,
    file_path: Path,
    language: str,
    enable_table: bool,
    enable_formula: bool,
    is_ocr: bool,
    page_range: Optional[str],
) -> Optional[str]:
    try:
        data = {
            "file_name": file_path.name,
            "language": language,
            "enable_table": enable_table,
            "enable_formula": enable_formula,
            "is_ocr": is_ocr,
        }
        if page_range:
            data["page_range"] = page_range

        resp = client.post(f"{AGENT_BASE_URL}/parse/file", json=data, timeout=30)
        if resp.status_code != 200:
            print(f"[Agent API] HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            return None
        result = resp.json()
        if result.get("code") != 0:
            print(f"[Agent API] Error: {result.get('msg', 'Unknown error')}", file=sys.stderr)
            return None
        task_id = result["data"]["task_id"]
        file_url = result["data"]["file_url"]
        print(f"[Agent API] Got upload URL, task_id: {task_id}")

        with open(file_path, "rb") as f:
            file_content = f.read()
        upload_resp = client.put(file_url, content=file_content, timeout=60)
        if upload_resp.status_code not in (200, 201):
            print(f"[Agent API] Upload failed: HTTP {upload_resp.status_code}", file=sys.stderr)
            return None
        print("[Agent API] File uploaded successfully")
        return task_id
    except Exception as e:
        print(f"[Agent API] Upload failed: {e}", file=sys.stderr)
        return None


def agent_poll_result(
    client: httpx.Client,
    task_id: str,
    poll_interval: int,
    timeout: int,
) -> Optional[str]:
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = client.get(f"{AGENT_BASE_URL}/parse/{task_id}", timeout=30)
            if resp.status_code != 200:
                elapsed = int(time.time() - start)
                print(f"[{elapsed}s] HTTP {resp.status_code}, retrying...", file=sys.stderr)
                time.sleep(poll_interval)
                continue
            result = resp.json()
            if result.get("code") != 0:
                print(f"[Agent API] Poll error: {result.get('msg')}", file=sys.stderr)
                return None
            data = result["data"]
            state = data.get("state", "")
            elapsed = int(time.time() - start)
            if state == "done":
                md_url = data.get("markdown_url", "")
                print(f"[{elapsed}s] Parse complete, downloading Markdown...")
                return md_url
            if state == "failed":
                err_msg = data.get("err_msg", "Unknown error")
                err_code = data.get("err_code", "")
                print(f"[{elapsed}s] Parse failed: {err_msg} (code: {err_code})", file=sys.stderr)
                return None
            label = STATE_LABELS.get(state, state)
            print(f"[{elapsed}s] {label}...")
        except Exception as e:
            elapsed = int(time.time() - start)
            print(f"[{elapsed}s] Poll error: {e}, retrying...", file=sys.stderr)
        time.sleep(poll_interval)
    print(f"[Agent API] Timeout after {timeout}s", file=sys.stderr)
    return None


def agent_download_markdown(client: httpx.Client, md_url: str, out_path: Path) -> bool:
    try:
        print(f"[Agent API] Downloading Markdown...")
        resp = client.get(md_url, timeout=60)
        if resp.status_code != 200:
            print(f"[Agent API] Download failed: HTTP {resp.status_code}", file=sys.stderr)
            return False
        md_content = resp.text
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md_content, encoding="utf-8")
        print(f"[Agent API] Saved Markdown to: {out_path}")
        print(f"  Content length: {len(md_content)} characters")
        return True
    except Exception as e:
        print(f"[Agent API] Download error: {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse documents to Markdown using MinerU API (document-parser skill).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
        "  parse.py --url https://example.com/doc.pdf --out output/doc.md\n"
        "  parse.py --file uploads/report.docx --out output/report.md\n"
        "  parse.py --url https://example.com/doc.pdf --out output/doc.md --is-ocr true --language ch",
    )
    parser.add_argument("--url", default=None, help="Remote document URL to parse.")
    parser.add_argument("--file", default=None, help="Local file path to parse (relative to workspace).")
    parser.add_argument("--out", required=True, help="Output Markdown file path (e.g. output/doc.md).")
    parser.add_argument("--language", default="ch", help="Document language (default: ch).")
    parser.add_argument("--model", default="vlm", help="Precision API model: pipeline, vlm, MinerU-HTML (default: vlm).")
    parser.add_argument("--enable-table", default="true", help="Enable table recognition (default: true).")
    parser.add_argument("--enable-formula", default="true", help="Enable formula recognition (default: true).")
    parser.add_argument("--is-ocr", default="false", help="Enable OCR for scanned documents (default: false).")
    parser.add_argument("--page-range", default=None, help="Page range for PDF, e.g. '1-10' or '5'.")
    parser.add_argument("--no-fallback", default="false", help="Disable fallback to Agent Lightweight API (default: false).")
    parser.add_argument("--poll-interval", type=int, default=3, help="Polling interval in seconds (default: 3).")
    parser.add_argument("--timeout", type=int, default=300, help="Maximum wait time in seconds (default: 300).")
    args = parser.parse_args()

    if not args.url and not args.file:
        print("ERROR: Must provide either --url or --file", file=sys.stderr)
        return 2
    if args.url and args.file:
        print("ERROR: Cannot provide both --url and --file", file=sys.stderr)
        return 2

    out_path = _resolve_out_path(args.out)
    enable_table = _bool_arg(args.enable_table)
    enable_formula = _bool_arg(args.enable_formula)
    is_ocr = _bool_arg(args.is_ocr)
    no_fallback = _bool_arg(args.no_fallback)

    file_path: Optional[Path] = None
    if args.file:
        file_path = _resolve_out_path(args.file)
        if not file_path.exists():
            print(f"ERROR: File not found: {file_path}", file=sys.stderr)
            return 2
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        print(f"Local file: {file_path} ({file_size_mb:.1f} MB)")

    print("=" * 60)
    print("Attempt 1: 🎯 Precision Extract API (vlm model)")
    print("=" * 60)

    precision_success = False
    with httpx.Client(follow_redirects=True, trust_env=False) as client:
        task_id = None
        if args.url:
            task_id = precision_parse_url(
                client, args.url, args.model, args.language,
                enable_table, enable_formula, is_ocr, args.page_range,
            )
        elif file_path:
            task_id = precision_upload_and_get_task(
                client, file_path, args.model, args.language,
                enable_table, enable_formula, is_ocr, args.page_range,
                args.poll_interval, args.timeout,
            )

        if task_id:
            zip_url = precision_poll_task(client, task_id, args.poll_interval, args.timeout)
            if zip_url:
                precision_success = precision_download_and_extract(client, zip_url, out_path)

    if precision_success:
        print("\n✅ Document parsed successfully with Precision API!")
        return 0

    if no_fallback:
        print("\n❌ Precision API failed and fallback is disabled.", file=sys.stderr)
        return 1

    print("\n" + "=" * 60)
    print("Attempt 2: ⚡ Agent Lightweight Extract API (fallback)")
    print("=" * 60)

    agent_success = False
    with httpx.Client(follow_redirects=True, trust_env=False) as client:
        if file_path:
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            if file_size_mb > 10:
                print(f"[Agent API] File size {file_size_mb:.1f}MB exceeds 10MB limit, skipping.", file=sys.stderr)
                print("\n❌ Both APIs failed. File too large for Agent API.", file=sys.stderr)
                return 1

        task_id = None
        if args.url:
            task_id = agent_parse_url(
                client, args.url, args.language,
                enable_table, enable_formula, is_ocr, args.page_range,
            )
        elif file_path:
            task_id = agent_upload_file(
                client, file_path, args.language,
                enable_table, enable_formula, is_ocr, args.page_range,
            )

        if task_id:
            md_url = agent_poll_result(client, task_id, args.poll_interval, args.timeout)
            if md_url:
                agent_success = agent_download_markdown(client, md_url, out_path)

    if agent_success:
        print("\n✅ Document parsed successfully with Agent Lightweight API!")
        return 0

    print("\n❌ Both Precision API and Agent Lightweight API failed.", file=sys.stderr)
    print("Possible reasons:", file=sys.stderr)
    print("  - File format not supported", file=sys.stderr)
    print("  - File exceeds size/page limits (Precision: 200MB/200pages, Agent: 10MB/20pages)", file=sys.stderr)
    print("  - Network connectivity issues", file=sys.stderr)
    print("  - API rate limit exceeded (HTTP 429)", file=sys.stderr)
    print("  - Invalid or inaccessible URL", file=sys.stderr)
    print("  - Token expired or invalid (Precision API)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
