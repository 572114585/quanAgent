# Attribution

This skill adapts workflow references, templates, and helper scripts from:

**Diagram Design**  
Author: Cathryn Lavery  
Repository: https://github.com/cathrynlavery/diagram-design  
License: MIT (see `LICENSE` in this directory)

DeepAgent-specific additions (not from upstream):

- `SKILL.md` rewritten for DeepAgents tool surface (`execute` / `render_html` / `ask_user_question` / workspace paths)
- Working style-guide and profiles live under `tmp/diagram-design/` because `skills/` is read-only
- `scripts/export_svg.py` — SVG export without `python -c` or temp Playwright snippets
- `scripts/extract_brand.py` — URL onboarding fetch that prints token candidates (does not write `skills/`)
- `references/export.md`, `onboarding.md`, `profiles.md` adapted to quanAgent sandbox rules
