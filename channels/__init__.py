"""多渠道接入包。

子包：
- channels.wechat: 个人微信渠道（ilink API，非流式）
- channels.wecom:  企业微信渠道（长连接，REPLACE 流式）

各渠道的 bridge 从 agent_core 导入 agent 单例；channel 专属配置
（WechatConfig/WeComConfig）保留在各自 config.py，不并入 agent_core.config。
"""
