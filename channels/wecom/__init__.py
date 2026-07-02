"""企业微信渠道包（长连接，REPLACE 流式）。

主要子模块：
- client:    build_ws_client() 构建 WebSocket 客户端
- handlers:  register(ws) 注册消息处理器
- bridge:    流式桥接（in-place replacement 语义）+ 多模态
- config:    WeComConfig

bridge 从 agent_core 导入 agent 单例。heavy 组件（build_ws_client/register/
stream_agent_reply）不在此 eager 导出，调用方从子模块直接 import，
避免导入即触发 agent 构建。
"""
from channels.wecom.config import WeComConfig

__all__ = ["WeComConfig"]
