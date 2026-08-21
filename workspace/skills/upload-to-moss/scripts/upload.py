#!/usr/bin/env python
"""Upload a workspace file to MOSS and print the public download URL as JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "agent_core").is_dir() and (parent / "tools").is_dir():
            return parent
    return here.parents[4]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload a local workspace file to MOSS and print download_url JSON.",
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Workspace-relative path under output/, tmp/, or uploads/.",
    )
    args = parser.parse_args()

    sys.path.insert(0, str(_repo_root()))
    from tools.moss_upload import upload_local_file

    result = upload_local_file(
        args.file,
        allowed_subdirs=("output", "tmp", "uploads"),
    )
    payload = {
        "ok": result.ok,
        "download_url": result.download_url,
        "bucket": result.bucket,
        "object_key": result.object_key,
    }
    if result.ok:
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    payload["error"] = result.error or "upload failed"
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
