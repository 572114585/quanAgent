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
import mimetypes
from pathlib import Path

from agent_core.config import OUTPUT_DIR

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
    ".zip": "application/zip",
}


# ----------------------------- run.py 风格（前端 SSE） -----------------------------


def snapshot_output_dir() -> set[tuple[str, int]]:
    """Take a snapshot of output/ directory: set of (relative_path, file_size)."""
    snapshot: set[tuple[str, int]] = set()
    for f in OUTPUT_DIR.rglob("*"):
        if f.is_file():
            try:
                rel = f.relative_to(OUTPUT_DIR).as_posix()
                snapshot.add((rel, f.stat().st_size))
            except OSError:
                continue
    return snapshot


def detect_new_artifacts(before: set[tuple[str, int]]) -> list[dict]:
    """Compare current output/ with the before snapshot, return list of artifact metadata dicts."""
    after = snapshot_output_dir()
    new_files = after - before
    artifacts = []
    for rel_path, size in new_files:
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
