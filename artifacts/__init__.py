"""产物检测统一模块。

消除原 run.py 与 channels/wechat/bridge.py 各自维护的产物检测重复实现。
两套风格的快照/diff 函数均在此导出（见 detector.py 说明）。
"""
from artifacts.detector import (
    detect_new_artifacts,
    diff_changed_artifacts,
    snapshot_output_dir,
    snapshot_output_dir_mtime,
)

__all__ = [
    "snapshot_output_dir",
    "detect_new_artifacts",
    "snapshot_output_dir_mtime",
    "diff_changed_artifacts",
]
