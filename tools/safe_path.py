"""研究素材落盘路径安全校验：强制落到 WORKSPACE_ROOT/tmp 下。"""
from __future__ import annotations

from pathlib import Path


class UnsafePathError(ValueError):
    """save_to 越界或非法时抛出。"""


def resolve_research_save_path(save_to: str) -> Path:
    """把 save_to 解析为 workspace/tmp 下的绝对路径。

    允许：
      - /tmp/research/foo.md（沙箱虚拟路径）
      - tmp/research/foo.md
      - research/foo.md（自动落到 tmp/research/）
      - 已在 workspace/tmp 下的绝对路径

    拒绝：
      - 空路径、含空字节
      - 绝对路径落在 tmp 外
      - .. 穿越到 tmp 外
      - 指向目录本身（必须是文件路径）
    """
    from agent_core.config import TMP_DIR, WORKSPACE_ROOT

    raw = (save_to or "").strip()
    if not raw:
        raise UnsafePathError("save_to 为空")
    if "\x00" in raw:
        raise UnsafePathError("save_to 含非法字符")

    tmp_root = TMP_DIR.resolve()
    ws_root = WORKSPACE_ROOT.resolve()

    # 统一分隔符，处理沙箱虚拟 /tmp/...
    normalized = raw.replace("\\", "/")
    if normalized.startswith("/tmp/") or normalized == "/tmp":
        rel = normalized[len("/tmp/") :] if normalized.startswith("/tmp/") else ""
        candidate = tmp_root / rel if rel else tmp_root
    elif normalized.startswith("tmp/") or normalized == "tmp":
        rel = normalized[len("tmp/") :] if normalized.startswith("tmp/") else ""
        candidate = tmp_root / rel if rel else tmp_root
    else:
        p = Path(raw)
        if p.is_absolute():
            candidate = p
        else:
            # 相对路径默认落到 tmp/ 下（research/x.md → tmp/research/x.md）
            candidate = tmp_root / raw

    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError) as e:
        raise UnsafePathError(f"无法解析路径: {e}") from e

    # 必须落在 TMP_DIR 内
    try:
        resolved.relative_to(tmp_root)
    except ValueError as e:
        raise UnsafePathError(
            f"save_to 必须位于 {tmp_root} 内，拒绝: {save_to}"
        ) from e

    # 额外确认仍在 workspace 内（防 TMP_DIR 配置异常）
    try:
        resolved.relative_to(ws_root)
    except ValueError as e:
        raise UnsafePathError(
            f"save_to 必须位于 workspace 内，拒绝: {save_to}"
        ) from e

    if resolved.exists() and resolved.is_dir():
        raise UnsafePathError(f"save_to 不能是目录: {save_to}")

    return resolved
