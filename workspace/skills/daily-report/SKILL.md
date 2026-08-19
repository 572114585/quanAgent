---
name: daily-report
description: "用快速联网搜索整理带日期和来源链接的日报。"
---

# Daily report

确认日期、主题和读者后，按主题执行最多 3 次 `web_search`，优先使用 `topic="news"`，把标题、URL 和摘要整理到 `/tmp/source_brief.md`。不自动抓取搜索结果正文；只有用户明确给出 URL 或要求打开网页时才使用 `web_fetch`。

按时间或主题分组撰写日报，所有事实使用 Markdown 链接引用。没有摘要支持的内容标为“资料不足/待核实”。交付前调用 `check_final_report`。
