# Onboarding — generate your skin from a design source

**Goal:** point the skill at a design source — a website, an installed skill, or pasted tokens — and write a **working** style guide so every future diagram in this workspace inherits that skin.

DeepAgent paths (non-negotiable):

- Shipped defaults (read-only): `skills/diagram-design/references/style-guide.md`
- Working copy (writable): `tmp/diagram-design/style-guide.md`
- Named profiles (writable): `tmp/diagram-design/profiles/<slug>.md`

Never edit files under `skills/`. Never write `~/.diagram-design/` or a project-root `.diagram-design` marker (workspace root is not a writable target).

Three source methods are supported. Jump to the relevant section:

- [§ URL](#url) — fetch a live website via `extract_brand.py`
- [§ Skill](#skill) — read another workspace skill that carries design tokens
- [§ Folder](#folder) — read a local design-system directory already in the workspace (`uploads/` or `tmp/`)

---

## The flow (all methods)

```
Source you provide (URL / skill name / folder path / pasted tokens)
      ↓
[1] read / fetch the source
      ↓
[2] extract dominant colors + fonts
      ↓
[3] map to semantic roles (paper, ink, muted, accent, …)
      ↓
[4] propose a tmp/diagram-design/style-guide.md diff
      ↓
[5] write the diff with ask_user_question approval
      ↓
[6] offer to save as tmp/diagram-design/profiles/<slug>.md
      ↓
future diagrams use your tokens
```

Gate-only choices use the same finish:

- **(d) Manual:** accept the user's tokens, `write_file` them into `tmp/diagram-design/style-guide.md` (start from the shipped file body), then offer to save a named profile.
- **(e) Default:** `read_file` the shipped guide and `write_file` the same body to `tmp/diagram-design/style-guide.md` so later runs skip the gate.

---

---

## § URL

### Invocation

> *"Onboard diagram-design to my site — `https://example.com`"*

---

### Step 1 — fetch the page

Run the packaged script (http(s) only, public IPs, 512KB cap). Do not use `python -c`, `curl`, or a headless browser.

```text
python skills/diagram-design/scripts/extract_brand.py --url https://example.com
```

The script prints guessed roles plus top hex colors. Confidence is low without a rendered browser — always confirm with `ask_user_question` before applying. If the site has multiple pages worth sampling, run the script 2–3 times and merge the palette signals.

---

## Step 2 — extract colors and fonts

### Colors

Parse the rendered CSS and screenshot:

- **Background color** of `<body>` or the dominant large region → `paper`
- **Primary text color** (body text) → `ink`
- **Secondary text color** (captions, meta) → `muted`
- **Most-used brand color** (CTA button, link, heading accent) → `accent`
- **Container / card background** slightly darker than paper → `paper-2`
- **Border / hairline color** → `rule` (convert to rgba of ink at ~0.12 opacity)

Prefer CSS custom properties when the site exposes them (`:root { --accent: …; }`). Otherwise pull via rendered `getComputedStyle` samples or a color-histogram pass over the screenshot.

### Fonts

Read the rendered `font-family` stack of:

- `<h1>` → `title` family
- `<body>` → `node-name` family  
- `<code>`, `<pre>`, or any mono-styled element → `sublabel` family

If the site has only one family, keep the schematic defaults for the missing roles (Instrument Serif for title, Geist Mono for mono). Don't force-pick a mono font that isn't on the site.

### Exact-font gate for brand-matched output

Do not replace a detected brand family with `serif`, `system-ui`, or `ui-monospace` merely to make the file dependency-free. A public font is part of the visual system.

1. Record the computed family and weight used by the sampled heading, body, and technical-label elements.
2. Trace each family to its source: an existing Google Fonts stylesheet, an installed/system stack, or a custom-hosted `@font-face`.
3. If it is available through Google Fonts, carry the exact family name, weights, and approved stylesheet into the style guide and generated HTML. The single-file allowlist accepts only a parsed HTTPS URL whose hostname is exactly `fonts.googleapis.com` and whose path is exactly `/css2`; prefix/lookalike hosts and other paths fail. Preserve an intentional system stack in order and verify the resolved family on the target machine.
4. A custom-hosted or paid font is not compatible with the default single-file allowlist. Label that role `fallback` unless the user separately approves and packages the font; never silently add a remote font URL or claim an exact match.
5. Verify the rendered output with `getComputedStyle`; a declared family that failed to load does not pass.

For a page containing bespoke diagrams or editorial figures, inspect their rendered font roles as well as the surrounding article. A figure-specific stylesheet may intentionally differ from the site's global heading/body stack.

---

## Step 3 — map to semantic roles

Propose a diff by filling this table:

| Role | Detected | Confidence |
|---|---|---|
| paper | `#f8f6f0` | high |
| ink | `#111111` | high |
| muted | `#6b6b68` | medium |
| accent | `#c73a2b` | high |
| … | … | … |

Flag low-confidence guesses so the user can correct before applying.

### Constraint checks

Before writing, validate:

- **AA contrast**: `ink` on `paper` ≥ 4.5:1. `muted` on `paper` ≥ 4.5:1 for body text.
- **Accent is the most saturated color**: not muted-ish, not near-grey.
- **paper ≠ pure white**: if the site uses `#ffffff`, fall back to `#fafaf7` to preserve Diagram Design's warm-neutral feel — or ask the user to confirm pure-white is intentional.

If any check fails, propose an adjusted value and explain why.

---

## Step 4 — preview the diff

Show the user what will change in `tmp/diagram-design/style-guide.md`. Only the tokens table — everything else stays the same.

```diff
-| `paper`  | `#f5f4ed` | `#1c1a17` |
-| `ink`    | `#0b0d0b` | `#f1efe7` |
-| `accent` | `#f7591f` | `#ff6a30` |
+| `paper`  | `#f8f6f0` | `#1a1815` |
+| `ink`    | `#111111` | `#efeee7` |
+| `accent` | `#c73a2b` | `#e05440` |
```

Also regenerate the dark variant via the inversion rule (`rgba(11,13,11, X)` → `rgba(ink-rgb, X)`).

Include a compact **brand fidelity receipt** with the preview:

- sampled URLs;
- detected paper, ink, muted, accent, surface, and rule values;
- title, body, and technical-label families with weights and source URLs;
- `exact` or `fallback` for each font role;
- any page-specific figure styling that should override the global site skin.

The receipt is required when the user says “match this site,” “use their branding,” or provides a page as the visual reference.

---

## Step 5 — apply

`read_file` the shipped `skills/diagram-design/references/style-guide.md`. If `tmp/diagram-design/profiles/default.md` does not exist, `write_file` that pristine body there first (see [`profiles.md`](profiles.md)). Never snapshot newly customized tokens as `default`.

Then `write_file` the customised guide to **`tmp/diagram-design/style-guide.md`**. Do not touch the shipped file.

After onboarding, generate one diagram into `output/` and confirm the new palette. If any type looks off, tune `muted` (often too dark or too light against the new `paper`).

---

## When URL onboarding fails

- **Site uses webfonts you can't replicate** (custom-hosted, paid): keep the schematic defaults for typography and skin only the colors.
- **Brand has 6+ colors** and you can't identify a clear hierarchy: pick one as `accent`, demote the rest to `muted` variants or ignore them. The schematic grammar only uses 5–7 roles.
- **Site is dark-mode first**: flip the inversion — treat their dark paper as the default `paper`, and generate a light variant via inversion.
- **Homepage is all imagery, no text**: ask for a blog or docs URL instead — text-heavy pages expose the type hierarchy.

---

## § Skill

Extract tokens from an installed Agent Skill that carries its own design system (e.g. a `brand-design` or `ui-kit` skill).

### Invocation

> *"Onboard diagram-design from my `acme-design` skill"*

Or the gate offers this as option (b) and the user names the skill.

### Step 1 — locate the skill

Only search `skills/<skill-name>/` inside this workspace (`ls` / `glob`). Do not search `~/.claude`, `~/.pi`, or other host skill directories. If the skill is not found, ask the user to confirm the name.

### Step 2 — read token sources

Glob the skill directory for any of these files and read them all:

| Priority | Pattern | What to look for |
|---|---|---|
| 1 | `*.css`, `colors*.css`, `tokens.css` | CSS custom properties in `:root { --color-*: …; }` |
| 2 | `tokens.json`, `design-tokens.json`, `*.tokens.json` | Style Dictionary / Figma token JSON |
| 3 | `SKILL.md`, `README.md` | Markdown tables listing colors, fonts, hex values |
| 4 | `style-guide.md`, `*design*.md` | Any narrative design documentation |
| 5 | `*.html` (preview/example files) | Inline `<style>` blocks — scan `:root` and `body` rules |

Read all matches and merge — CSS custom properties take priority over inferred values from HTML.

### Step 3 — extract colors and fonts

**From CSS custom properties:**
Map variable names to semantic roles using name-heuristics:

| If the variable name contains… | Map to role |
|---|---|
| `background`, `bg`, `paper`, `surface`, `canvas` | `paper` |
| `foreground`, `text`, `body`, `ink`, `on-surface` | `ink` |
| `muted`, `subtle`, `secondary`, `caption` | `muted` |
| `accent`, `brand`, `primary`, `cta`, `highlight` | `accent` |
| `border`, `rule`, `divider`, `outline` | `rule` |
| `mono`, `code`, `pre` | `sublabel` font |

**From JSON tokens:** follow the same heuristics on key names. If the JSON follows Style Dictionary format (`{ "color": { "brand": { "value": "#…" } } }`), flatten the path and apply heuristics to the leaf key.

**From Markdown tables:** look for rows with hex values (`#rrggbb`) adjacent to role-like words. A row like `| accent | #eb6c36 |` maps directly.

**Fonts:** look for `font-family` rules, `@import` or `@font-face` declarations, and Markdown mentions of font names alongside size/weight.

### Step 4 — map, validate, propose diff

Same as the URL method: fill the role table, run contrast checks, show the diff, ask for approval before writing.

### When skill extraction is ambiguous

- **Skill has no CSS or token files**: fall back to reading all `.md` files and look for hex values mentioned in prose. Surface what you found and ask the user to confirm mappings before applying.
- **Multiple accent candidates**: list them and ask the user to pick one. Don't guess.
- **Skill is dark-mode first**: ask whether to treat the dark values as the `paper`/`ink` defaults or to invert.

---

## § Folder

Extract tokens from a local directory — a checked-out design system repo, a Figma export, or any folder the user points you at.

### Invocation

> *"Onboard diagram-design from my design system at `uploads/brand/` or `tmp/design-tokens/`"*

Or the gate offers this as option (c) and the user provides the path.

### Step 1 — discover files

Glob the folder (recursively, up to 3 levels deep) for:

```
**/*.css
**/*.scss        (read @forward / $variable declarations)
**/tokens.json
**/*.tokens.json
**/design-tokens.json
**/colors.json
**/*style-guide*.md
**/*design-system*.md
**/README.md
**/*.html        (scan <style> blocks only)
```

If the result set is large (>20 files), prefer files in the root and files whose names contain `color`, `token`, `brand`, `palette`, `style`, or `theme`.

### Step 2 — read and merge

Read every discovered file. Apply the same extraction logic as the Skill method (§ Skill → Step 3). CSS custom properties and JSON tokens take priority over inferred values from prose.

**SCSS variables:** treat `$variable-name: value;` the same as a CSS custom property — apply name heuristics to `$variable-name`.

**Figma token JSON** (Figma Tokens Plugin format):

```json
{ "colors": { "brand": { "primary": { "value": "#eb6c36", "type": "color" } } } }
```

Walk the tree; the leaf `value` fields are the colors, the path segments supply the role heuristic.

### Step 3 — map, validate, propose diff

Same as the URL method: run contrast checks, show the full diff against current `tmp/diagram-design/style-guide.md` (or shipped defaults if missing), and write only after the user approves.

### When folder extraction is ambiguous

- **No structured token files, only prose docs**: read every `.md` in the root and extract hex values found near role-like words. Show the user a table of what you inferred — don't silently apply uncertain mappings.
- **Multiple themes / color schemes found**: list them, ask the user which one to use as the diagram skin.
- **Folder has zero readable files**: tell the user and ask for a more specific path or switch to manual token entry.

---

## Multiple clients? Save a profile

After every onboarding method, offer to save the completed guide as a named client profile. Follow [`profiles.md`](profiles.md) for the canonical home-directory library, metadata header, strict slug validation, and project marker. A project with a `.diagram-design` marker reads its profile directly, so parallel client workspaces do not overwrite one shared working copy.
