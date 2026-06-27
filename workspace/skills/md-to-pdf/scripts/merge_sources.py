#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
merge_sources.py — 多源 Markdown 合并(sequential / thematic / standalone)

用法:
    python skills/md-to-pdf/scripts/merge_sources.py \
        --inputs '["output/ch1.md","output/ch2.md"]' \
        --strategy sequential \
        --out output/merged.md

策略:
    sequential  按 inputs 顺序拼接,每份之间插分页符(---)
    thematic    提取所有 H1/H2,按主题重新归类成新章节
    standalone  每个 MD 作为独立"部"(Part),带部首页

图片硬规则:默认保留所有图片(![](...))。
    - 相对路径按源文件目录重写为 file:// 绝对路径,避免合并后路径失效
    - http(s):// / data: / 已是绝对路径的,原样保留
    - 仅当显式传 --strip-images 时才移除图片
"""
import argparse
import json
import re
import sys
from pathlib import Path


PAGE_BREAK = "\n\n---\n\n"

# Markdown 图片语法:![alt](src) 或 ![alt](src "title")
IMG_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

# 绝对路径判定:Windows 盘符(D:\, C:/)或 Unix 根路径(/...)
ABS_PATH_RE = re.compile(r'^(?:[A-Za-z]:[\\/]|/|\\\\)')

# 不应改写的 scheme
URL_SCHEME_RE = re.compile(r'^(?:https?|ftp|data|file):', re.IGNORECASE)


def rewrite_image_paths(content: str, source_dir: Path) -> str:
    """把相对图片路径按源文件目录重写为 file:// 绝对路径。

    保留:http(s)://、data:、ftp:、file:、已是绝对路径的
    重写:相对路径 → file:///abs/path
    """
    def repl(m):
        alt = m.group(1)
        src_raw = m.group(2).strip()
        # 拆出可能的 title:src "title"
        parts = src_raw.split(None, 1)
        path_part = parts[0]
        title_part = parts[1] if len(parts) > 1 else None

        # 跳过网络/数据 URI
        if URL_SCHEME_RE.match(path_part):
            return m.group(0)
        # 跳过已经是绝对路径的
        if ABS_PATH_RE.match(path_part):
            return m.group(0)
        # 相对路径 → 绝对 file:// URI
        try:
            abs_path = (source_dir / path_part).resolve()
            new_src = abs_path.as_uri()
        except (OSError, ValueError):
            # 路径解析失败,原样保留
            return m.group(0)
        if title_part:
            title_clean = title_part.strip().strip('"').strip("'")
            return f'![{alt}]({new_src} "{title_clean}")'
        return f'![{alt}]({new_src})'

    return IMG_RE.sub(repl, content)


def strip_images(content: str) -> str:
    """移除所有图片引用。仅当用户显式要求时调用。"""
    # 移除独立图片行(行首到行尾只有图片)
    content = re.sub(r'^\s*!\[[^\]]*\]\([^)]+\)\s*$', '', content, flags=re.MULTILINE)
    # 移除行内图片
    content = IMG_RE.sub('', content)
    # 清理多余空行
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content


def count_images(content: str) -> int:
    """统计 MD 中的图片数量。"""
    return len(IMG_RE.findall(content))


def read_md(path: Path, rewrite_images: bool = True) -> str:
    if not path.exists():
        print(f"[ERROR] 文件不存在: {path}", file=sys.stderr)
        sys.exit(1)
    text = path.read_text(encoding="utf-8")
    if rewrite_images:
        text = rewrite_image_paths(text, path.parent)
    return text


# ── sequential:顺序拼接 ──────────────────────────────────
def merge_sequential(inputs: list, contents: list) -> str:
    """按顺序拼接,每份之间插分页符。"""
    return PAGE_BREAK.join(contents)


# ── thematic:按主题重组 ──────────────────────────────────
def merge_thematic(inputs: list, contents: list) -> str:
    """提取所有 H1/H2,按主题词归类。

    逻辑:把每个 H2 及其下内容作为一个"主题块",按 H2 文本归类。
    相同主题的块合并到同一 H1 下。H1 作为新章节标题。
    """
    # 解析每个 MD 为 (h1, [(h2, body), ...])
    docs = []
    for path, content in zip(inputs, contents):
        h1_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        doc_title = h1_match.group(1).strip() if h1_match else path.stem
        # 切分:每个 H2 开启一个块
        sections = re.split(r'^(##\s+.+)$', content, flags=re.MULTILINE)
        # sections[0] 是 H2 之前的内容(含 H1 与导言)
        preamble = sections[0] if sections else ""
        blocks = []
        i = 1
        while i < len(sections):
            h2_line = sections[i]
            body = sections[i + 1] if i + 1 < len(sections) else ""
            h2_text = re.sub(r'^##\s+', '', h2_line).strip()
            blocks.append((h2_text, h2_line + "\n" + body))
            i += 2
        docs.append((doc_title, preamble, blocks))

    # 按主题词归类:相同 H2 文本合并
    topics = {}
    topic_order = []
    for doc_title, preamble, blocks in docs:
        for h2_text, block in blocks:
            if h2_text not in topics:
                topics[h2_text] = []
                topic_order.append(h2_text)
            topics[h2_text].append((doc_title, block))

    # 重组输出
    out = ["# 主题汇编\n"]
    for topic in topic_order:
        out.append(f"\n## {topic}\n")
        for doc_title, block in topics[topic]:
            # 块前标注来源文档
            out.append(f"\n*来源:{doc_title}*\n")
            out.append(block)
        out.append(PAGE_BREAK)

    return "\n".join(out)


# ── standalone:独立"部" ─────────────────────────────────
def merge_standalone(inputs: list, contents: list) -> str:
    """每个 MD 作为独立 Part,带部首页。"""
    parts = []
    for i, (path, content) in enumerate(zip(inputs, contents), 1):
        # 提取原标题作为 Part 名
        h1_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        original_title = h1_match.group(1).strip() if h1_match else path.stem

        # 部首页
        part_opener = f"# 第 {i} 部 · {original_title}\n\n"
        # 原 H1 降级为 H2(避免与部首 H1 冲突)
        content_demoted = re.sub(r'^#\s+', '## ', content, flags=re.MULTILINE)
        parts.append(part_opener + content_demoted)

    return PAGE_BREAK.join(parts)


# ── 主流程 ────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="多源 Markdown 合并(sequential / thematic / standalone)"
    )
    parser.add_argument("--inputs", required=True,
                        help='JSON 数组,如 "[\\"a.md\\",\\"b.md\\"]"')
    parser.add_argument("--strategy", default="sequential",
                        choices=["sequential", "thematic", "standalone"],
                        help="合并策略(默认 sequential)")
    parser.add_argument("--out", required=True, help="输出合并后的 MD 路径")
    parser.add_argument("--strip-images", action="store_true",
                        help="移除所有图片(默认保留图片;仅当显式指定才移除)")
    parser.add_argument("--no-rewrite-paths", action="store_true",
                        help="不把相对图片路径重写为 file:// 绝对路径(默认会重写)")
    args = parser.parse_args()

    try:
        inputs_raw = json.loads(args.inputs)
    except json.JSONDecodeError as e:
        print(f"[ERROR] --inputs JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(inputs_raw, list) or len(inputs_raw) == 0:
        print("[ERROR] --inputs 必须是非空 JSON 数组", file=sys.stderr)
        sys.exit(1)

    inputs = [Path(p) for p in inputs_raw]
    rewrite = not args.no_rewrite_paths
    contents = [read_md(p, rewrite_images=rewrite) for p in inputs]

    # 合并前图片计数(用于事后核对是否丢图)
    before_counts = [count_images(c) for c in contents]
    before_total = sum(before_counts)

    # 仅当用户显式要求时才移除图片
    if args.strip_images:
        contents = [strip_images(c) for c in contents]
        after_strip_counts = [count_images(c) for c in contents]
        after_strip_total = sum(after_strip_counts)
    else:
        after_strip_total = before_total

    if args.strategy == "sequential":
        merged = merge_sequential(inputs, contents)
    elif args.strategy == "thematic":
        merged = merge_thematic(inputs, contents)
    elif args.strategy == "standalone":
        merged = merge_standalone(inputs, contents)
    else:
        print(f"[ERROR] 未知策略: {args.strategy}", file=sys.stderr)
        sys.exit(1)

    # 合并后图片计数(thematic 重组可能影响顺序但不应丢图)
    after_total = count_images(merged)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(merged, encoding="utf-8")

    size = out_path.stat().st_size
    h1_count = len(re.findall(r'^#\s+', merged, re.MULTILINE))
    h2_count = len(re.findall(r'^##\s+', merged, re.MULTILINE))

    print(f"[OK] 合并完成: {out_path}")
    print(f"     策略: {args.strategy}")
    print(f"     源文件数: {len(inputs)}")
    print(f"     H1 数: {h1_count}, H2 数: {h2_count}")
    print(f"     大小: {size} 字节 ({size / 1024:.1f} KB)")
    print(f"     图片:源共 {before_total} 张,合并后 {after_total} 张"
          f"{'(--strip-images 已移除 ' + str(before_total - after_strip_total) + ' 张)' if args.strip_images else ''}")
    if not args.strip_images and after_total < before_total:
        print(f"     [WARN] 合并后图片数少于源总数,可能丢图,请检查 thematic 策略的 H2 切块")
    if not args.no_rewrite_paths and after_total > 0:
        print(f"     图片路径:已按源文件目录重写为 file:// 绝对路径")


if __name__ == "__main__":
    main()
