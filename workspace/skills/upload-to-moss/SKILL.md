---
name: upload-to-moss
description: "把工作区内的本地文件上传到 MOSS（MOSS_BUCKET 桶下的 quan/ 目录）并返回可分享的下载链接。仅在用户明确要求上传、分享或获取下载地址时使用；output/ 最终产物会自动上传，不要在每次生成后重复调用。"
allowed-tools: execute
---

# 上传文件到 MOSS

将 `output/`、`tmp/` 或 `uploads/` 下的普通文件上传到 MOSS（桶名来自环境变量 `MOSS_BUCKET`，对象前缀为 `quan/`），并返回公开下载 URL。

最终产物写入 `output/` 后系统会自动上传；本 skill 只用于用户明确说「上传 / 分享 / 给我下载链接」的场景（含 `tmp/`、`uploads/` 里的文件）。

## 必须遵守的命令格式

1. **命令必须单行**：`execute(command=...)` 禁止反斜杠续行或裸换行。
2. **只调用本 skill 自带脚本**。禁止 `write_file` 自写 `.py`，禁止 `python -c`，禁止 `curl`。
3. 路径含空格时用双引号包住 `--file` 的值。

## 执行步骤

1. 确认用户给出的路径存在、是普通文件且可读；目录、符号链接和不存在的路径均应报错，不要上传。
2. 运行：

```
python skills/upload-to-moss/scripts/upload.py --file output/report.pdf
```

3. 解析 stdout JSON：
   - `ok` 必须为 `true`
   - `download_url` 必须为非空字符串
4. 成功时只把 `download_url` 回给用户，不要自行拼接 URL、修改文件名或重试上传。

## 错误处理

- 文件不存在、不是普通文件、越界或不在 `output/` `tmp/` `uploads/`：不执行上传，说明具体原因。
- 脚本非零退出：把 `error`（存在时）或 stderr 告诉用户，不要声称上传成功。
- MOSS 未配置（缺少 Access Key / Secret Key）：说明当前无法上传，不要编造链接。

## 示例

```
python skills/upload-to-moss/scripts/upload.py --file output/report.pdf
python skills/upload-to-moss/scripts/upload.py --file "uploads/季度汇报.docx"
```
