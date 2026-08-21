---
name: send_cc_msg
description: "向企业通讯工具发送 CC 消息。用户明确要求发送通知、预警或任务进展时使用；支持普通文本、标题、Banner 和图片链接。"
allowed-tools: execute
---

# 发送 CC 消息

使用本 Skill 自带脚本向企业通讯工具发送 CC 消息。该操作会产生外部通知副作用，必须先获得用户确认后再执行脚本。

## 输入参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `receiver_id` | 是 | 接收者 ID、员工工号或用户 ID；多个 ID 使用英文或中文逗号分隔 |
| `message` | 是 | 消息正文 |
| `title` | 否 | 消息标题 |
| `banner_url` | 否 | Banner 图片 URL |
| `thumbnail_url` | 否 | 单张图片 URL |
| `thumbnail_urls` | 否 | 多张图片 URL，使用逗号分隔；优先于 `thumbnail_url` |
| `thumbnail_text` | 否 | 图片链接显示文本 |

## 使用方式

```bash
python skills/send-cc-msg/scripts/send_cc_msg.py --receiver_id "00109726" --message "车辆预警：请及时处理"
```

带标题和图片：

```bash
python skills/send-cc-msg/scripts/send_cc_msg.py --receiver_id "00109726" --message "车辆预警详情" --title "异常通知" --thumbnail_url "https://example.com/image.jpg"
```

执行前必须确认：

1. 接收者 ID 已由用户提供或明确授权使用。
2. 消息正文、标题和图片链接符合用户意图。
3. 已向用户说明即将发送外部消息，并获得本次发送确认。

## 输出

脚本 stdout 输出 JSON。成功结果包含 `success: true`、`receiver_id` 和 `receiveridtype`；失败时 `success` 为 `false`，不得向用户声称发送成功。

## 配置

参见 `skills/send-cc-msg/references/config.md`。凭据必须通过运行环境变量提供，不得写入 Skill 文件或消息参数。

## 注意事项

- 脚本会对消息内容进行双重 Base64 编码，以符合 CC 接口协议。
- 脚本会自动尝试 `receiveridtype=1、2、3`。
- 未配置 CC 环境变量时不要执行发送命令，应先提示用户配置。
