---
name: document-builder
description: "把用户需求整理成有来源链接的 Markdown/HTML 文档，并按需交付 PDF。"
---

# Document builder

适用于需要大纲、多个章节和最终质量检查的文档任务；简单问答或单页编辑不使用本流程。

## 流程

1. 明确主题、读者、输出格式和必须回答的问题。
2. 最多执行 3 次 `web_search`。每次记录标题、URL 和摘要到 `/tmp/source_brief.md`；普通问题只搜索一次，只有无结果时才补搜一次。
3. 根据用户需求制定简短大纲，资料不足的部分标为“资料不足/待核实”。
4. 逐章交给 `section-writer`，只使用 source brief、用户文件和已有 Markdown 链接；不让写作者自行联网。
5. 合并章节，引用使用 `[标题](URL)`，不使用内部证据 ID、运行 ID 或覆盖矩阵。
6. 调用 `check_final_report`，修复占位符、TODO、缺失链接、关键点和过时预测后再交付。

## 约束

- 搜索摘要和 URL 是默认联网资料。只有用户明确提供 URL 或要求打开网页时才使用 `web_fetch`。
- 不把未经摘要支持的推断写成事实；无法核实就明确说明缺口。
- PDF、Word、Excel 和图表按对应 skill 处理；远程 PDF 先提示用户上传文件。
