"""调研素材落盘校验：强制 ## 抓取记录 全文格式。"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
import json
from pathlib import Path

from langchain_core.tools import tool

_FETCH_HEADER_RE = re.compile(r"^##\s*抓取记录\b", re.MULTILINE)
_FETCH_CHARS_RE = re.compile(
    r"^(?:-\s*)?\*\*\s*字数\s*\*\*\s*[:：]\s*(\d+)",
    re.MULTILINE,
)

# 深度档位期望的最低单条抓取字数（允许截断，但过短视为失败）
_MIN_CHARS_BY_DEPTH = {
    "brief": 800,
    "standard": 3000,
    "in-depth": 5000,
}

# 与 research-strategies skill 的 top N 对齐
_MIN_FETCH_BLOCKS_BY_DEPTH = {
    "brief": 1,
    "standard": 4,
    "in-depth": 8,
}
_MAX_MATERIAL_BYTES = 20 * 1024 * 1024


@dataclass
class ResearchMaterialReport:
    ok: bool
    path: str
    fetch_block_count: int
    char_counts: list[int]
    errors: list[str]

    def summary(self) -> str:
        if self.ok:
            total = sum(self.char_counts)
            return (
                f"[research_ok] {self.path}: "
                f"{self.fetch_block_count} 条抓取记录，合计约 {total} 字"
            )
        return "[research_fail] " + "; ".join(self.errors)


def validate_research_material(
    path: str | Path,
    *,
    depth: str = "standard",
    min_fetch_blocks: int | None = None,
) -> ResearchMaterialReport:
    """检查 research 素材是否含 save_to 产生的全文抓取记录。

    Args:
        path: /tmp/research/*.md 或 workspace 相对路径
        depth: brief | standard | in-depth
        min_fetch_blocks: 最少抓取条数；默认 brief=1, standard=4, in-depth=8
    """
    p = Path(path)
    depth_key = (depth or "standard").strip().lower()
    if depth_key not in _MIN_CHARS_BY_DEPTH:
        depth_key = "standard"
    if min_fetch_blocks is None:
        min_fetch_blocks = _MIN_FETCH_BLOCKS_BY_DEPTH[depth_key]
    min_chars = _MIN_CHARS_BY_DEPTH[depth_key]

    errors: list[str] = []
    if not p.is_file():
        return ResearchMaterialReport(
            ok=False,
            path=str(p),
            fetch_block_count=0,
            char_counts=[],
            errors=[f"文件不存在: {p}"],
        )
    try:
        size_bytes = p.stat().st_size
    except OSError as exc:
        return ResearchMaterialReport(
            ok=False,
            path=str(p),
            fetch_block_count=0,
            char_counts=[],
            errors=[f"无法读取文件元数据: {p}: {exc}"],
        )
    if size_bytes > _MAX_MATERIAL_BYTES:
        return ResearchMaterialReport(
            ok=False,
            path=str(p),
            fetch_block_count=0,
            char_counts=[],
            errors=[
                f"文件大小 {size_bytes} 字节，超过校验上限 {_MAX_MATERIAL_BYTES} 字节"
            ],
        )

    text = p.read_text(encoding="utf-8", errors="replace")
    headers = list(_FETCH_HEADER_RE.finditer(text))
    if not headers:
        return ResearchMaterialReport(
            ok=False,
            path=str(p),
            fetch_block_count=0,
            char_counts=[],
            errors=[
                f"{p} 缺少「## 抓取记录」。禁止用自写要点笔记冒充素材；"
                "必须用 web_fetch(..., save_to=该路径) 落盘全文。"
            ],
        )

    char_counts = [int(m.group(1)) for m in _FETCH_CHARS_RE.finditer(text)]
    # 若元数据字数缺失，用相邻抓取块粗估
    if len(char_counts) < len(headers):
        # 简单按 header 切分估长度
        spans = [m.start() for m in headers] + [len(text)]
        estimated: list[int] = []
        for i in range(len(headers)):
            chunk = text[spans[i] : spans[i + 1]]
            # 去掉 header 行后估正文
            body = "\n".join(chunk.splitlines()[6:])
            estimated.append(len(body.strip()))
        char_counts = estimated

    short = [c for c in char_counts if c < min_chars]
    if len(headers) < min_fetch_blocks:
        errors.append(
            f"抓取记录仅 {len(headers)} 条，{depth_key} 要求至少 {min_fetch_blocks} 条"
        )
    if short:
        errors.append(
            f"有 {len(short)} 条抓取字数 < {min_chars}（{depth_key} 下限），"
            "请提高 max_content_chars 或更换可抓取来源"
        )

    return ResearchMaterialReport(
        ok=not errors,
        path=str(p),
        fetch_block_count=len(headers),
        char_counts=char_counts,
        errors=errors,
    )


@tool
def check_research_material(
    path: str,
    depth: str = "standard",
) -> str:
    """检查 ``/tmp/research`` 素材是否达到抓取条数与正文深度要求。

    本工具直接验证 ``## 抓取记录``、每条字数和深度档位阈值。审查研究素材时
    必须优先调用它，不要用 ``grep``、``wc``、``python -c`` 或 PowerShell
    手工组合统计。该工具只读，且路径被限制在工作区 ``tmp`` 子树。
    """
    from tools.safe_path import UnsafePathError, resolve_research_save_path

    try:
        resolved = resolve_research_save_path(path)
    except UnsafePathError as exc:
        return json.dumps(
            {"ok": False, "path": path, "errors": [str(exc)]},
            ensure_ascii=False,
            indent=2,
        )

    report = validate_research_material(
        resolved,
        depth=depth,
    )
    payload = asdict(report)
    payload["path"] = path
    payload["summary"] = report.summary()
    return json.dumps(payload, ensure_ascii=False, indent=2)
