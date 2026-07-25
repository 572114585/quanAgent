#!/usr/bin/env python3
"""Package a generated Three.js sculpt factory (.ts) into a standalone HTML preview.

DeepAgent delivery path: interactive HTML under workspace/output/, previewable via
artifact iframe and screenshotable with render_html (preserveDrawingBuffer).

Usage (cwd = workspace root):
  python skills/object-sculptor/scripts/package_html.py \\
    --factory tmp/sculpt/run/Object.generated.ts \\
    --out output/object-sculpt.html \\
    --title "Object Sculpt"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


THREE_VERSION = "0.160.0"
THREE_MODULE = f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}/build/three.module.js"
THREE_ADDONS = f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}/examples/jsm/"


def _skip_type(text: str, start: int) -> int:
    """Skip a TypeScript type starting at `start` (first char of the type)."""
    i = start
    n = len(text)
    depth_angle = 0
    depth_paren = 0
    depth_bracket = 0
    depth_brace = 0
    while i < n:
        ch = text[i]
        if ch in "\"'":
            quote = ch
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if ch == "<":
            depth_angle += 1
        elif ch == ">":
            if depth_angle:
                depth_angle -= 1
        elif ch == "(":
            depth_paren += 1
        elif ch == ")":
            if depth_paren:
                depth_paren -= 1
            elif depth_angle == 0 and depth_bracket == 0 and depth_brace == 0:
                break
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]":
            if depth_bracket:
                depth_bracket -= 1
        elif ch == "{":
            # Object type literals are only entered when already inside a type
            # expression that expected braces. A bare `{` after a return-type
            # annotation is the function body — stop before it.
            if depth_brace == 0 and depth_angle == 0 and depth_paren == 0 and depth_bracket == 0:
                break
            depth_brace += 1
        elif ch == "}":
            if depth_brace:
                depth_brace -= 1
                i += 1
                continue
            break
        elif (
            ch in ",=;:"
            and depth_angle == 0
            and depth_paren == 0
            and depth_bracket == 0
            and depth_brace == 0
        ):
            break
        elif (
            ch == "\n"
            and depth_angle == 0
            and depth_paren == 0
            and depth_bracket == 0
            and depth_brace == 0
        ):
            j = i + 1
            while j < n and text[j] in " \t":
                j += 1
            if j < n and text[j] in "|&":
                i = j
                continue
            # end of a single-line type; object types use braces so stay in loop
            break
        i += 1
    return i


def _strip_type_aliases(text: str) -> str:
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        m = re.match(
            r"(?:export\s+)?(?:type|interface)\s+[A-Za-z_][\w.]*"
            r"(?:\s*<[^;{]*>)?\s*",
            text[i:],
        )
        if not m:
            out.append(text[i])
            i += 1
            continue
        j = i + m.end()
        if j < n and text[j] == "{":
            depth = 0
            while j < n:
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
        elif j < n and text[j] == "=":
            j += 1
            # Consume a full type expression, including intersections / unions
            # with object literals: `A & { ... } | B`
            while True:
                while j < n and text[j] in " \t\n":
                    j += 1
                if j >= n:
                    break
                if text[j] == "{":
                    depth = 0
                    while j < n:
                        if text[j] == "{":
                            depth += 1
                        elif text[j] == "}":
                            depth -= 1
                            if depth == 0:
                                j += 1
                                break
                        j += 1
                else:
                    j = _skip_type(text, j)
                while j < n and text[j] in " \t\n":
                    j += 1
                if j < n and text[j] in "|&":
                    j += 1
                    continue
                # `_skip_type` stops before `{`; object literals still belong to the alias
                if j < n and text[j] == "{":
                    continue
                break
        while j < n and text[j] in "; \t\n":
            if text[j] == ";":
                j += 1
                break
            j += 1
        i = j
    return "".join(out)


def _consume_braced(text: str, start: int) -> int:
    """Consume a `{ ... }` block starting at `start` (must be `{`)."""
    j = start
    n = len(text)
    depth = 0
    while j < n:
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return n


def _strip_as_assertions(text: str) -> str:
    text = re.sub(r"\s+as\s+const\b", "", text)
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        m = re.match(r"\s+(?:as|satisfies)\s+", text[i:])
        if m and (i == 0 or text[i - 1].isalnum() or text[i - 1] in ")]}'\""):
            j = i + m.end()
            while j < n and text[j] in " \t\n":
                j += 1
            if j < n and text[j] == "{":
                j = _consume_braced(text, j)
            else:
                j = _skip_type(text, j)
                while j < n and text[j] in " \t\n":
                    j += 1
                # `as Foo & { ... }` / `satisfies Bar | { ... }`
                while j < n and text[j] in "|&":
                    j += 1
                    while j < n and text[j] in " \t\n":
                        j += 1
                    if j < n and text[j] == "{":
                        j = _consume_braced(text, j)
                    else:
                        j = _skip_type(text, j)
                    while j < n and text[j] in " \t\n":
                        j += 1
            i = j
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _strip_colon_types(text: str) -> str:
    """Remove `: Type` annotations after identifiers / ) in value positions."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] != ":":
            out.append(text[i])
            i += 1
            continue

        # Ternary? look back for `?` not part of `?:`
        # Skip object keys in type positions already removed; here we strip value annotations.
        # Heuristic: previous non-space is identifier, ), or ]
        k = len(out) - 1
        while k >= 0 and out[k] in " \t":
            k -= 1
        if k < 0:
            out.append(text[i])
            i += 1
            continue
        prev = out[k]
        # optional `?:` — drop the whole annotation including ?
        optional = False
        if prev == "?" and k >= 1:
            k2 = k - 1
            while k2 >= 0 and out[k2] in " \t":
                k2 -= 1
            if k2 >= 0 and (out[k2].isalnum() or out[k2] == "_" or out[k2] in ")"):
                optional = True
                prev_ok = True
                prev = out[k2]
            else:
                prev_ok = False
        else:
            prev_ok = prev.isalnum() or prev == "_" or prev in ")]"

        # Don't strip labels in object literals used as values: `{ a: 1 }` —
        # after identifier, if next type looks like a value start (digit/quote/{/[), keep colon.
        if not prev_ok:
            out.append(text[i])
            i += 1
            continue

        j = i + 1
        while j < n and text[j] in " \t\n":
            j += 1
        if j >= n:
            out.append(text[i])
            i += 1
            continue

        # Object-literal value: `: {` or `: [` or `: "string"` or `: number` or `: function`
        # vs type annotation `: THREE.Group` / `: boolean` / `: string | null`
        # If the token after colon is a lowercase JS primitive keyword used as type, strip.
        # If it's a constructor call start like `new` or `{` for value — keep.
        rest = text[j:]
        if rest.startswith(("new ", "new\t", "new\n", "function", "async ", "await ", "class ")):
            out.append(text[i])
            i += 1
            continue
        if rest[0] in "\"'`":
            # String literal value OR string-literal union type:
            # `label: "x"` vs `mode: 'a' | 'b' = 'a'`
            quote = rest[0]
            q = 1
            while q < len(rest):
                if rest[q] == "\\":
                    q += 2
                    continue
                if rest[q] == quote:
                    q += 1
                    break
                q += 1
            while q < len(rest) and rest[q] in " \t\n":
                q += 1
            if q < len(rest) and rest[q] in "|&":
                pass  # fall through — treat as type
            else:
                out.append(text[i])
                i += 1
                continue
        elif rest[0] in "{0123456789-+!":
            # object/number literal values — keep colon
            out.append(text[i])
            i += 1
            continue

        # Array literal values vs tuple types: `["root"]` / `[1, 2]` vs `[number, number]`
        if rest[0] == "[":
            k3 = 1
            while k3 < len(rest) and rest[k3] in " \t\n":
                k3 += 1
            if k3 < len(rest) and (
                rest[k3] in "\"'`{[0123456789-+!"
                or rest.startswith(("true", "false", "null", "undefined"), k3)
            ):
                out.append(text[i])
                i += 1
                continue

        # Param / return annotations often start with THREE., primitives, arrays, unions.
        type_start = re.match(
            r"(THREE\.|[A-Z]|\[|[\"']|boolean\b|number\b|string\b|void\b|any\b|never\b|"
            r"unknown\b|object\b|bigint\b|symbol\b|Record\b|Partial\b|Readonly\b|"
            r"Array\b|Map\b|Set\b|Promise\b|null\b|undefined\b)",
            rest,
        )
        if not type_start:
            out.append(text[i])
            i += 1
            continue

        # Avoid stripping object-literal values like `{ count: numberOfItems }` where
        # the value is a lowercase identifier — only strip when previous token looks
        # like a parameter / binding (after `(` `,` or `)` for return types).
        p = k
        while p >= 0 and out[p] in " \t\n":
            p -= 1
        # walk back over identifier to see delimiter
        if p >= 0 and (out[p].isalnum() or out[p] == "_"):
            q = p
            while q >= 0 and (out[q].isalnum() or out[q] == "_"):
                q -= 1
            while q >= 0 and out[q] in " \t\n":
                q -= 1
            delim = out[q] if q >= 0 else "("
            # Also allow `const|let|var name: Type`
            keyword = ""
            if delim not in "(),":
                r = q
                while r >= 0 and (out[r].isalnum() or out[r] == "_"):
                    r -= 1
                keyword = "".join(out[r + 1 : q + 1]) if q >= r + 1 else ""
            if delim not in "()," and keyword not in {"const", "let", "var"}:
                # likely object property value, keep
                out.append(text[i])
                i += 1
                continue
        elif prev == ")":
            # Return / predicate annotation only when followed by `{` or `=>`
            # (not ternary `cond ? fn() : fallback`).
            end_probe = _skip_type(text, j)
            k4 = end_probe
            while k4 < n and text[k4] in " \t\n":
                k4 += 1
            if not (k4 < n and (text[k4] == "{" or text.startswith("=>", k4))):
                out.append(text[i])
                i += 1
                continue
        else:
            out.append(text[i])
            i += 1
            continue

        if optional:
            while out and out[-1] in " \t":
                out.pop()
            if out and out[-1] == "?":
                out.pop()

        end = _skip_type(text, j)
        i = end
        continue

    return "".join(out)


def _strip_trailing_generics(text: str) -> str:
    """Remove TS generics on constructors / functions: Foo<Bar>(), new Set<T>()."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] != "<":
            out.append(text[i])
            i += 1
            continue
        # Only strip if previous token is an identifier (or `.identifier`)
        k = len(out) - 1
        while k >= 0 and out[k] in " \t":
            k -= 1
        if k < 0 or not (out[k].isalnum() or out[k] == "_"):
            out.append(text[i])
            i += 1
            continue
        # Don't strip comparison `a < b` — require `>` then `(` or another `<` chain end before `(`
        j = i + 1
        depth = 1
        while j < n and depth:
            if text[j] == "<":
                depth += 1
            elif text[j] == ">":
                depth -= 1
            elif text[j] in "\n;{}=":
                # unlikely generic
                break
            j += 1
        if depth != 0:
            out.append(text[i])
            i += 1
            continue
        # j is past `>`; allow whitespace then `(` or another generic already closed
        k2 = j
        while k2 < n and text[k2] in " \t":
            k2 += 1
        if k2 < n and text[k2] in "({.":
            # `.` covers `Foo<T>.bar` rare; `(` is constructor/call; `{` for JSX-like rare
            if text[k2] == ".":
                # Prefer keep for `Array<T>.isArray` — still valid to strip Array<T>
                pass
            i = j
            continue
        # comparisons / other — keep
        out.append(text[i])
        i += 1
    return "".join(out)


def strip_typescript(source: str) -> str:
    """Best-effort TS→JS for generator output (no full TypeScript parser)."""
    text = source.replace("\r\n", "\n")
    text = _strip_type_aliases(text)
    text = _strip_as_assertions(text)
    text = _strip_colon_types(text)
    text = _strip_trailing_generics(text)
    # function name<T>(
    text = re.sub(r"(export\s+function\s+[A-Za-z_][\w]*)\s*<[^>]*>", r"\1", text)
    text = re.sub(r"(function\s+[A-Za-z_][\w]*)\s*<[^>]*>", r"\1", text)
    # type predicates: (x): x is string =>
    text = re.sub(
        r"\)\s*:\s*[A-Za-z_][\w]*\s+is\s+[A-Za-z_][\w.|<\s\[\]>]*(?=\s*=>)",
        ")",
        text,
    )
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def detect_frame_helper(js_source: str) -> str | None:
    match = re.search(r"export\s+function\s+(frame\w+ForReview)\s*\(", js_source)
    return match.group(1) if match else None


def detect_lights_helper(js_source: str) -> str | None:
    match = re.search(r"export\s+function\s+(create\w+LookDevLights)\s*\(", js_source)
    return match.group(1) if match else None


def detect_configure_renderer(js_source: str) -> str | None:
    match = re.search(
        r"export\s+function\s+(configure\w+LookDevRenderer)\s*\(", js_source
    )
    return match.group(1) if match else None


def build_html(factory_js: str, title: str, background: str = "#1a1a1a") -> str:
    frame_fn = detect_frame_helper(factory_js) or ""
    lights_fn = detect_lights_helper(factory_js) or ""
    configure_fn = detect_configure_renderer(factory_js) or ""

    safe_factory = factory_js.replace("</script>", "<\\/script>")

    frame_call = (
        f"    {frame_fn}(camera, model);\n"
        if frame_fn
        else "    // no frame*ForReview helper — using default camera\n"
    )
    lights_call = (
        f"    scene.add({lights_fn}());\n"
        if lights_fn
        else (
            "    scene.add(new THREE.AmbientLight(0xffffff, 0.55));\n"
            "    const key = new THREE.DirectionalLight(0xffffff, 1.1);\n"
            "    key.position.set(3, 5, 4);\n"
            "    scene.add(key);\n"
        )
    )
    configure_call = (
        f"    {configure_fn}(renderer);\n" if configure_fn else ""
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <!--
    Generated by object-sculptor package_html.py
    Three.js {THREE_VERSION} (ESM + importmap) — aligned with web-viz-libraries
    preserveDrawingBuffer:true required for render_html PNG capture
  -->
  <script type="importmap">
  {{
    "imports": {{
      "three": "{THREE_MODULE}",
      "three/addons/": "{THREE_ADDONS}"
    }}
  }}
  </script>
  <style>
    html, body {{ margin: 0; height: 100%; overflow: hidden; background: {background}; }}
    canvas {{ display: block; }}
    #info {{
      position: absolute; top: 10px; left: 10px; color: #fff;
      font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      text-shadow: 0 1px 2px #000; pointer-events: none;
    }}
  </style>
</head>
<body>
  <div id="info">拖拽旋转 · 滚轮缩放 · 右键平移 · Object Sculptor</div>
  <script type="module">
import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';
{safe_factory}

    const scene = new THREE.Scene();
    scene.background = new THREE.Color('{background}');

    const camera = new THREE.PerspectiveCamera(
      45, window.innerWidth / window.innerHeight, 0.01, 2000
    );
    camera.position.set(2.5, 2.0, 3.5);

    const renderer = new THREE.WebGLRenderer({{ antialias: true, preserveDrawingBuffer: true }});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);
    document.body.appendChild(renderer.domElement);
{configure_call}
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;

{lights_call}
    const model = createSculptModel({{ castShadow: true, receiveShadow: true }});
    scene.add(model);
{frame_call}
    controls.target.set(0, 0, 0);
    controls.update();

    function animate() {{
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }}
    animate();

    window.addEventListener('resize', () => {{
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    }});
  </script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Package a sculpt *.generated.ts factory into standalone HTML."
    )
    parser.add_argument(
        "--factory",
        required=True,
        help="Path to generate_threejs_factory output (*.generated.ts or .js)",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output HTML path (prefer output/<name>.html)",
    )
    parser.add_argument("--title", default="Object Sculpt", help="HTML <title>")
    parser.add_argument(
        "--background",
        default="#1a1a1a",
        help="Scene background color (CSS/hex)",
    )
    parser.add_argument(
        "--also-js",
        action="store_true",
        help="Also write stripped JS next to the HTML (<stem>.factory.js)",
    )
    args = parser.parse_args(argv)

    factory_path = Path(args.factory).expanduser()
    out_path = Path(args.out).expanduser()
    if not factory_path.is_file():
        print(f"error: factory not found: {factory_path}", file=sys.stderr)
        return 1

    source = factory_path.read_text(encoding="utf-8")
    if factory_path.suffix.lower() in {".ts", ".tsx"}:
        js = strip_typescript(source)
    else:
        js = source

    if "createSculptModel" not in js:
        print(
            "error: factory must export createSculptModel "
            "(run sculpt.py generate first)",
            file=sys.stderr,
        )
        return 1

    if "import * as THREE from 'three'" not in js and 'import * as THREE from "three"' not in js:
        js = "import * as THREE from 'three';\n" + js

    html = build_html(js, title=args.title, background=args.background)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(str(out_path.resolve()))

    if args.also_js:
        js_path = out_path.with_suffix(".factory.js")
        js_path.write_text(js, encoding="utf-8")
        print(str(js_path.resolve()))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
