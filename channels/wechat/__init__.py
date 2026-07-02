"""个人微信渠道包（ilink API，非流式）。

主要子模块：
- api:       ilink Bot API 客户端
- monitor:   长轮询消息监听
- bridge:    消息 → agent → 回复 桥接（含多模态处理、产物自动投递）
- sender:    发送文本/文件（分段、内联图片）
- accounts:  多账号绑定管理
- config:    WechatConfig（媒体限制、API 配置）

bridge 从 agent_core 导入 agent 单例。heavy 组件（Monitor/Sender/handle_message）
不在此 eager 导出，调用方从子模块直接 import，避免导入即触发 agent 构建。
"""
from channels.wechat.config import WechatConfig

__all__ = ["WechatConfig"]
