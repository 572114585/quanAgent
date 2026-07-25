"""检索深度、摘要加厚、research 落盘校验相关单测。"""
import json
from pathlib import Path

from tools.fetch_utils import extract_key_info
from tools.research_validate import check_research_material, validate_research_material
from tools.search.base import SearchQuery


def test_extract_key_info_is_thicker_than_eight_bullets():
    body = (
        "# 技术白皮书\n\n"
        + ("这是一段足够长的正文介绍，用于验证摘录长度。" * 40)
        + "\n\n市场规模达到 120 亿美元，CAGR 为 25%。\n"
        + "另一行数据：吞吐量 10000 QPS，延迟 12ms。\n"
    )
    summary = extract_key_info(body, title="技术白皮书")
    assert "摘录" in summary or "标题" in summary
    assert len(summary) >= 400
    assert "120" in summary or "CAGR" in summary or "QPS" in summary


def test_validate_research_requires_fetch_headers(tmp_path: Path):
    shallow = tmp_path / "shallow.md"
    shallow.write_text("# 笔记\n- 要点1\n- 要点2\n", encoding="utf-8")
    report = validate_research_material(shallow, depth="standard")
    assert report.ok is False
    assert any("抓取记录" in e for e in report.errors)


def test_validate_research_accepts_save_to_format(tmp_path: Path):
    good = tmp_path / "good.md"
    chunks = []
    for i in range(4):
        body = ("正文段落内容充实，用于满足 standard 深度字数下限。" * 120)
        chunks.append(
            f"\n\n{'='*60}\n## 抓取记录 | 2026-07-20 12:0{i}\n"
            f"- **URL**: https://example.com/{i}\n"
            f"- **标题**: Doc {i}\n"
            f"- **阶段**: 深度\n"
            f"- **字数**: {len(body)}\n"
            f"{'='*60}\n\n{body}\n"
        )
    good.write_text("".join(chunks), encoding="utf-8")
    report = validate_research_material(good, depth="standard", min_fetch_blocks=3)
    assert report.ok is True
    assert report.fetch_block_count >= 3


def test_check_research_material_tool_uses_safe_virtual_path(
    tmp_path: Path,
    monkeypatch,
):
    from tools import safe_path

    material = tmp_path / "research.md"
    body = "正文内容充实。" * 700
    chunks = [
        (
            f"## 抓取记录 | 2026-07-21 10:0{i}\n"
            f"**字数**: {len(body)}\n\n{body}\n"
        )
        for i in range(4)
    ]
    material.write_text("\n".join(chunks), encoding="utf-8")
    monkeypatch.setattr(safe_path, "resolve_research_save_path", lambda path: material)

    payload = json.loads(
        check_research_material.invoke(
            {"path": "/tmp/research/topic.md", "depth": "standard"}
        )
    )

    assert payload["ok"] is True
    assert payload["path"] == "/tmp/research/topic.md"
    assert payload["fetch_block_count"] == 4


def test_search_query_carries_search_depth():
    sq = SearchQuery(query="x", max_results=10, search_depth="advanced")
    assert sq.search_depth == "advanced"
