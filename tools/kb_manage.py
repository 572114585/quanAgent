"""知识库管理 CLI:批量入库、查看统计、清空命名空间。
用法:
  python -m tools.kb_manage ingest <dir_or_file> [--namespace default]
  python -m tools.kb_manage stats [--namespace default]
  python -m tools.kb_manage clear [--namespace default]
"""
import argparse
import asyncio
from pathlib import Path

# 加载 .env 到 os.environ,确保子进程(extract.py)能读到 MINERU_API_TOKEN
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from tools.kb_tool import get_kb, _kb_instances

SUPPORTED_EXT = {".pdf", ".docx", ".pptx", ".txt", ".md", ".html", ".png", ".jpg", ".jpeg"}


async def cmd_ingest(target: str, namespace: str):
    kb = get_kb(namespace)
    p = Path(target)
    if p.is_file():
        files = [p]
    elif p.is_dir():
        files = [f for f in p.rglob("*") if f.suffix.lower() in SUPPORTED_EXT]
    else:
        print(f"路径不存在: {target}")
        return
    if not files:
        print(f"未找到支持的文件(支持: {SUPPORTED_EXT})")
        return
    print(f"待入库 {len(files)} 个文件到命名空间 [{namespace}]...")
    success, failed = 0, 0
    for f in files:
        try:
            count = await kb.add_document(str(f))
            print(f"  OK {f.name} -> {count} chunks")
            success += 1
        except Exception as e:
            print(f"  FAIL {f.name} -> {e}")
            failed += 1
    print(f"完成:成功 {success},失败 {failed}")


async def cmd_stats(namespace: str):
    kb = get_kb(namespace)
    s = kb.stats()
    print(f"命名空间: {namespace}")
    for k, v in s.items():
        print(f"  {k}: {v}")


async def cmd_clear(namespace: str):
    import shutil

    kb = get_kb(namespace)
    shutil.rmtree(kb.persist_dir, ignore_errors=True)
    _kb_instances.pop(namespace, None)
    print(f"已清空命名空间: {namespace}")


def main():
    ap = argparse.ArgumentParser(description="知识库管理工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_ingest = sub.add_parser("ingest", help="批量入库")
    p_ingest.add_argument("target", help="文件或目录路径")
    p_ingest.add_argument("--namespace", default="default")
    p_stats = sub.add_parser("stats", help="查看统计")
    p_stats.add_argument("--namespace", default="default")
    p_clear = sub.add_parser("clear", help="清空命名空间")
    p_clear.add_argument("--namespace", default="default")
    args = ap.parse_args()
    if args.cmd == "ingest":
        asyncio.run(cmd_ingest(args.target, args.namespace))
    elif args.cmd == "stats":
        asyncio.run(cmd_stats(args.namespace))
    elif args.cmd == "clear":
        asyncio.run(cmd_clear(args.namespace))


if __name__ == "__main__":
    main()
