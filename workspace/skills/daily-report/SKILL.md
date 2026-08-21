---
name: daily-report
description: "Fast dated reports assembled from bounded parallel web research and source links."
allowed-tools: web_research web_search web_fetch check_final_report
metadata:
  network_capable: true
  read_only: true
  expected_latency: "5-55s"
  supports_batch: true
---

# Daily report

Confirm the date, topic, and audience. For multi-angle topics, plan up to
three distinct evidence gaps and call `web_research` through the bounded
research dispatcher rather than issuing serial searches. Prefer `topic="news"`
for current events. Use `web_fetch` only for explicitly selected URLs.

Keep title, URL, and summary provenance beside each factual claim. If the
dispatcher returns partial or timed-out results, say so and do not invent the
missing facts. Run `check_final_report` before delivery.
