"""无需 Shell 的工作区文件检查与原子覆盖工具。"""
from __future__ import annotations

import json

from langchain_core.tools import tool


@tool
def inspect_file(
    file_path: str,
    tail_lines: int = 0,
    count_literals: list[str] | None = None,
) -> str:
    """检查工作区文本文件。

    返回文件字节数、行数、字符数和修改时间；可通过 ``tail_lines`` 读取末尾
    N 行，通过 ``count_literals`` 统计若干单行字面量的出现次数。需要文件
    元数据、尾部内容或计数时必须优先使用本工具，不要调用 ``execute``、
    ``python -c`` 或 PowerShell。路径可使用 ``/tmp/...``、``/output/...``
    等工作区虚拟路径。
    """
    from sandbox import backend

    result = backend.inspect_file(
        file_path,
        tail_lines=tail_lines,
        count_literals=count_literals,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def replace_file(file_path: str, content: str) -> str:
    """原子创建或完整覆盖工作区 UTF-8 文本文件。

    仅允许写入 ``/tmp`` 与 ``/output``。当目标文件可能已经存在，或需要清空/
    完整替换文件时使用本工具；不要先用 ``rm``、Shell 重定向、``python -c``
    或 PowerShell 删除/截断文件。首次创建且确定目标不存在时仍可使用内置
    ``write_file``。
    """
    from sandbox import backend

    result = backend.replace_file(file_path, content)
    if result.error:
        return json.dumps(
            {"ok": False, "path": file_path, "error": result.error},
            ensure_ascii=False,
            indent=2,
        )
    return json.dumps(
        {"ok": True, "path": result.path or file_path, "operation": "replaced"},
        ensure_ascii=False,
        indent=2,
    )
