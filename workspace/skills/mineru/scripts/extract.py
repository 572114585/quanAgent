"""
MinerU 文档提取脚本(适配 deepagent 框架)。

调度策略(优先级从高到低):
  1. mineru-open-api extract  (需 token,支持多格式/大文件/VLM 模型)
  2. mineru-open-api flash-extract (免 token,仅 Markdown,限 10MB/20 页)
  3. 全部失败 → 非零退出码 + 错误汇总

本脚本是 mineru-open-api CLI 的包装器,不直接写 MinerU HTTP 调用,
复用 CLI 的上传/轮询/下载逻辑。CLI 通过 `npx --no-install` 调用全局安装包。
"""
import argparse
import os
import shutil
import subprocess
import sys


def _find_npx() -> str:
    """定位 npx 完整路径。

    Windows 上 npx 是 npx.cmd,subprocess.run(shell=False) 不会自动按
    PATHEXT 补全扩展名,必须用 shutil.which 拿到完整路径。找不到则报错。
    """
    npx = shutil.which("npx")
    if not npx:
        raise FileNotFoundError(
            "找不到 npx。请确保 Node.js 已安装且在 PATH 中,且 mineru-open-api "
            "已通过 `npm install -g mineru-open-api` 安装。"
        )
    return npx

# extract 模式触发降级的退出码集合(这些不代表"不可恢复",而是"换模式可能成功")。
# 126/127:CLI 未安装;429 限流 CLI 会以非零退出;其余非零统一尝试降级。
_DOWNGRADE_EXIT_CODES = frozenset({1, 2})

# flash-extract 的硬限制(超出直接报错,不降级——已是最底层)。
FLASH_MAX_SIZE_MB = 10
FLASH_MAX_PAGES = 20


def _get_token() -> str | None:
    """读取 MinerU API token。

    优先级:MINERU_API_TOKEN(.env 实际变量名)> MINERU_TOKEN(CLI 文档变量名)。
    返回 None 表示无 token(此时 extract 不可用,直接走 flash-extract)。
    """
    return os.environ.get("MINERU_API_TOKEN") or os.environ.get("MINERU_TOKEN")


def _run_mineru(subcmd: str, extra_args: list[str], *, token: str | None,
                timeout: int) -> tuple[int, str, str]:
    """调用 mineru-open-api 子命令,返回 (returncode, stdout, stderr)。

    token 仅在 extract 子命令时通过 --token 传入(flash-extract 免 token)。
    用 --token 显式传,避免 CLI 读 MINERU_TOKEN 环境变量名与 .env 的
    MINERU_API_TOKEN 不一致的问题。
    """
    try:
        npx = _find_npx()
    except FileNotFoundError as e:
        return 127, "", str(e)

    cmd = [npx, "--no-install", "mineru-open-api", subcmd]
    if token and subcmd == "extract":
        cmd += ["--token", token]
    cmd += extra_args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", f"命令超时({timeout}s): {' '.join(cmd)}"
    except FileNotFoundError as e:
        return 127, "", str(e)


def _build_extract_args(args: argparse.Namespace) -> list[str]:
    """构造 extract 子命令的参数列表。"""
    out: list[str] = [args.input, "-o", args.output, "-f", args.format]
    if args.model:
        out += ["--model", args.model]
    if args.language:
        out += ["--language", args.language]
    if args.pages:
        out += ["--pages", args.pages]
    if args.ocr:
        out.append("--ocr")
    if args.no_formula:
        out.append("--formula=false")
    if args.no_table:
        out.append("--table=false")
    return out


def _build_flash_args(args: argparse.Namespace) -> list[str]:
    """构造 flash-extract 子命令的参数列表。

    flash-extract 仅支持 Markdown 输出,忽略 --format/--model。
    """
    out: list[str] = [args.input, "-o", args.output]
    if args.language:
        out += ["--language", args.language]
    if args.pages:
        out += ["--pages", args.pages]
    if args.ocr:
        out.append("--ocr")
    if args.no_formula:
        out.append("--formula=false")
    if args.no_table:
        out.append("--table=false")
    return out


def _try_extract(args: argparse.Namespace, token: str) -> tuple[bool, str]:
    """尝试 extract 模式。返回 (是否成功, 信息/错误)。"""
    cli_args = _build_extract_args(args)
    code, stdout, stderr = _run_mineru(
        "extract", cli_args, token=token, timeout=args.timeout
    )
    if code == 0:
        return True, stdout.strip() or f"extract 成功,输出到 {args.output}"
    return False, f"[extract 退出码 {code}] {stderr.strip() or stdout.strip()}"


def _try_flash(args: argparse.Namespace) -> tuple[bool, str]:
    """尝试 flash-extract 模式。返回 (是否成功, 信息/错误)。"""
    cli_args = _build_flash_args(args)
    code, stdout, stderr = _run_mineru(
        "flash-extract", cli_args, token=None, timeout=args.timeout
    )
    if code == 0:
        return True, stdout.strip() or f"flash-extract 成功,输出到 {args.output}"
    return False, f"[flash-extract 退出码 {code}] {stderr.strip() or stdout.strip()}"


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="extract.py",
        description="MinerU 文档提取(优先 extract,降级 flash-extract)",
    )
    parser.add_argument("input", help="输入文件路径或 URL")
    parser.add_argument(
        "-o", "--output", default="output/",
        help="输出路径(文件或目录,默认 output/)",
    )
    parser.add_argument(
        "-f", "--format", default="md",
        help="输出格式:md/json/html/latex/docx(逗号分隔,默认 md;仅 extract 生效)",
    )
    parser.add_argument("--model", default="", help="extract 模型:vlm/pipeline/html")
    parser.add_argument("--language", default="ch", help="文档语言(默认 ch)")
    parser.add_argument("--pages", default="", help="页码范围,如 1-10,15")
    parser.add_argument("--ocr", action="store_true", help="启用 OCR(扫描件)")
    parser.add_argument("--no-formula", action="store_true", help="禁用公式识别")
    parser.add_argument("--no-table", action="store_true", help="禁用表格识别")
    parser.add_argument(
        "--timeout", type=int, default=900,
        help="单次调用超时秒数(默认 900)",
    )
    parser.add_argument(
        "--mode", default="auto",
        help="强制模式:auto(默认,extract→flash 降级)/extract(仅 extract)/flash(仅 flash)",
    )
    args = parser.parse_args()

    # 校验 mode
    mode = args.mode.lower()
    if mode not in ("auto", "extract", "flash"):
        print(f"错误:无效的 --mode '{args.mode}',可选 auto/extract/flash", file=sys.stderr)
        return 2

    token = _get_token()
    errors: list[str] = []
    used_mode = ""

    # 1. extract(extract-only 或 auto 且有 token)
    if mode in ("auto", "extract"):
        if not token:
            if mode == "extract":
                print(
                    "错误:--mode extract 需要 token,但未找到 MINERU_API_TOKEN 环境变量。",
                    file=sys.stderr,
                )
                return 3
            errors.append("无 token(MINERU_API_TOKEN 未设置),跳过 extract")
        else:
            ok, msg = _try_extract(args, token)
            if ok:
                used_mode = "extract"
                print(f"[OK] {msg}")
                print(f"[INFO] 使用模式: extract", file=sys.stderr)
                return 0
            errors.append(msg)
            # extract 失败时,auto 模式继续降级

    # 2. flash-extract(auto 或 flash-only)
    if mode in ("auto", "flash"):
        ok, msg = _try_flash(args)
        if ok:
            used_mode = "flash-extract"
            print(f"[OK] {msg}")
            print(
                f"[INFO] 使用模式: flash-extract"
                + ("(已从 extract 降级)" if errors else ""),
                file=sys.stderr,
            )
            return 0
        errors.append(msg)

    # 3. 全部失败
    print("=" * 60, file=sys.stderr)
    print("错误:所有提取模式均失败。", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(
        "排查建议:\n"
        "  1. 检查网络(需访问 mineru.net)\n"
        "  2. extract 模式:确认 token 有效(https://mineru.net/apiManage/token)\n"
        "  3. flash-extract:文件需 ≤10MB 且 ≤20 页\n"
        "  4. 确认 mineru-open-api 已安装:npm install -g mineru-open-api",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
