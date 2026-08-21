"""产物检测统一模块。

合并原 run.py L182-232 与 channels/wechat/bridge.py L65-91 的两份产物检测实现。

两份实现语义不同，故本模块提供两套函数，各自调用方使用对应风格：
- run.py 风格（前端 SSE 用）：snapshot_output_dir() → set[(rel_path, size)]，
  detect_new_artifacts(before) → list[dict]（含 name/path/url/mime/size，按 name 排序）。
  检测"新增或 size 变更"的文件（set 差集）。
- wechat 风格（文件投递用）：snapshot_output_dir_mtime() → dict[Path, (mtime, size)]，
  diff_changed_artifacts(before, after) → list[Path]（新增或 mtime/size 变更，按 mtime 升序）。
  供 sender.send_file 逐个投递。

两套都集中在此模块，调用方无本地实现。
"""
import logging
import mimetypes
import subprocess
import sys
from pathlib import Path

from agent_core.config import OUTPUT_DIR

logger = logging.getLogger(__name__)

# 产物 mime 映射（合并自 run.py 的 16 项）。缺失时回退到 mimetypes.guess_type。
_MIME_MAP = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".html": "text/html",
    ".svg": "image/svg+xml",
    ".zip": "application/zip",
}


# ----------------------------- run.py 风格（前端 SSE） -----------------------------


def snapshot_output_dir() -> set[tuple[str, int, int]]:
    """Take a snapshot of output/ directory: set of (relative_path, file_size, mtime_ns)."""
    snapshot: set[tuple[str, int, int]] = set()
    for f in OUTPUT_DIR.rglob("*"):
        if f.is_file():
            try:
                st = f.stat()
                rel = f.relative_to(OUTPUT_DIR).as_posix()
                snapshot.add((rel, st.st_size, getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))))
            except OSError:
                continue
    return snapshot


def detect_new_artifacts(before: set) -> list[dict]:
    """Compare current output/ with the before snapshot, return list of artifact metadata dicts."""
    after = snapshot_output_dir()
    sample = next(iter(before), None) if before else None
    if sample is not None and len(sample) == 2:
        before_ps = {(p, s) for p, s in before}  # type: ignore[misc]
        after_ps = {(p, s) for p, s, _m in after}
        changed = after_ps - before_ps
        new_files = [(p, s, m) for p, s, m in after if (p, s) in changed]
    else:
        new_files = list(after - before)  # type: ignore[operator]
    artifacts = []
    for rel_path, size, _mtime in new_files:
        name = Path(rel_path).name
        ext = Path(rel_path).suffix.lower()
        mime = _MIME_MAP.get(ext, mimetypes.guess_type(name)[0] or "application/octet-stream")
        artifacts.append({
            "name": name,
            "path": rel_path,
            "url": f"/output/{rel_path}",
            "mime": mime,
            "size": size,
        })
    artifacts.sort(key=lambda a: a["name"])
    return artifacts


def finalize_diagram_pairs(before: set) -> None:
    """Ensure changed diagram HTML files have a sibling SVG before detection.

    ``diagram-design`` treats HTML as the editable source and SVG as a default
    delivery artifact. The model normally runs ``export_svg.py`` itself, but a
    missed tool call should not make the result depend on model wording. This
    narrow fallback only applies to changed HTML files that look like an
    accessible inline-SVG diagram; ordinary HTML reports are left untouched.
    """
    workspace_root = Path(OUTPUT_DIR).resolve().parent
    script = workspace_root / "skills" / "diagram-design" / "scripts" / "export_svg.py"
    if not script.is_file():
        logger.warning("diagram-design SVG fallback unavailable: %s", script)
        return

    for artifact in detect_new_artifacts(before):
        if artifact.get("mime") != "text/html":
            continue
        html_path = OUTPUT_DIR / str(artifact["path"])
        svg_path = html_path.with_suffix(".svg")
        if svg_path.exists() or not _looks_like_diagram_html(html_path):
            continue
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--file",
                    f"output/{artifact['path']}",
                    "--out",
                    svg_path.relative_to(workspace_root).as_posix(),
                ],
                cwd=workspace_root,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning(
                "diagram-design SVG fallback failed for %s: %s",
                artifact["path"],
                exc,
            )
            continue
        if result.returncode != 0:
            logger.warning(
                "diagram-design SVG fallback failed for %s: %s",
                artifact["path"],
                (result.stderr or result.stdout).strip(),
            )
        else:
            logger.info(
                "diagram-design SVG fallback created %s",
                svg_path.relative_to(workspace_root).as_posix(),
            )


def _looks_like_diagram_html(path: Path) -> bool:
    try:
        html = path.read_text(encoding="utf-8").lower()
    except (OSError, UnicodeError):
        return False
    if "diagram-design" in html:
        return True
    return "<svg" in html and 'role="img"' in html and "aria-labelledby" in html


def attach_moss_urls(artifacts: list[dict]) -> list[dict]:
    """Upload each output/ artifact to MOSS and swap `url` for the public link.

    Soft-degrades: unconfigured MOSS or a single-file failure leaves the local
    `/output/...` URL in place. Successful uploads also set `mossUrl`.
    """
    if not artifacts:
        return artifacts
    from tools.moss_upload import moss_settings, try_upload_output_file

    if not moss_settings().configured:
        return artifacts
    attached: list[dict] = []
    for art in artifacts:
        updated = dict(art)
        rel_path = str(art.get("path") or "")
        if not rel_path:
            attached.append(updated)
            continue
        download_url = try_upload_output_file(
            OUTPUT_DIR / rel_path,
            workspace_root=Path(OUTPUT_DIR).resolve().parent,
        )
        if download_url:
            updated["url"] = download_url
            updated["mossUrl"] = download_url
        attached.append(updated)
    return attached


# ----------------------------- wechat 风格（文件投递） -----------------------------


def snapshot_output_dir_mtime() -> dict[Path, tuple[float, int]]:
    """扫描 output/ 目录，返回 {文件路径: (mtime, size)} 快照。

    用于 wechat bridge：在 agent 调用前后各拍一次快照，diff 出本轮新增/变更的产物。
    """
    if not OUTPUT_DIR.exists():
        return {}
    return {
        p: (p.stat().st_mtime, p.stat().st_size)
        for p in OUTPUT_DIR.rglob("*")
        if p.is_file()
    }


def diff_changed_artifacts(
    before: dict[Path, tuple[float, int]],
    after: dict[Path, tuple[float, int]],
) -> list[Path]:
    """对比两次快照，返回本轮新增或被改写的文件路径（按 mtime 升序）。"""
    changed = [
        p
        for p, sig in after.items()
        if p not in before or before[p] != sig
    ]
    # 新文件优先（mtime 更晚的），稳定的排序便于日志观察
    changed.sort(key=lambda p: after[p][0])
    return changed
