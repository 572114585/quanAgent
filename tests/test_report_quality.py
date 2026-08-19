from datetime import date

from agent_core.report_quality import KeyPoint, ReportContract, evaluate_report_quality


def _obsolete_report_frozen_benchmark():
    pass


def test_report_quality_rejects_unresolved_references_and_past_forecasts():
    result = evaluate_report_quality(
        """# Report
## 核心结论
2025年下半年预计产品将发布。[2]
""",
        ReportContract(require_source_urls=True),
        current_date=date(2026, 8, 13),
    )
    assert not result.ok
    assert any("unresolved numeric" in item for item in result.errors)
    assert any("no source URL" in item for item in result.errors)
    assert any("horizon is already past" in item for item in result.errors)


def test_report_quality_scores_weighted_key_points_and_focus():
    result = evaluate_report_quality(
        """# Report
## 执行摘要
真实重建与生成式补全应分开。单图背面不可观测，多视图提供更多观测。

## 核心分析
前馈路线降低延迟，但需要按输入和硬件比较。
""",
        ReportContract(
            required_key_points=[
                KeyPoint("boundary", (r"重建.*生成",), 2),
                KeyPoint("observability", (r"单图.*不可观测",), 1),
                KeyPoint("representations", (r"Mesh.*3DGS",), 1),
            ],
            priority_topics=[r"重建", r"前馈"],
            min_priority_paragraph_share=0.2,
            require_source_urls=False,
        ),
    )
    assert result.metrics["weighted_key_point_recall"] == 0.75
    assert "representations" in result.missing_key_points
    assert result.metrics["priority_paragraph_share"] >= 0.2
