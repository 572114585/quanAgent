---
name: document-builder
description: "Build source-linked Markdown or HTML documents using bounded parallel research."
allowed-tools: web_research web_search web_fetch inspect_file replace_file check_final_report
metadata:
  network_capable: true
  read_only: false
  expected_latency: "5-55s research stage"
  supports_batch: true
---

# Document builder

Use this workflow for outlines, multi-section documents, and final quality
checks. Define the topic, audience, output format, and evidence gaps first.
For external facts, dispatch distinct queries through `web_research`; keep the
shared limit of six queries and the 55-second research deadline. Do not search
serially merely to fill a source list.

Search summaries and URLs are default evidence. Fetch only explicitly selected
pages. Give every factual claim a Markdown URL, mark unsupported claims as
“资料不足，待核实”, and keep `section-writer` offline. Run
`check_final_report` before delivery.
