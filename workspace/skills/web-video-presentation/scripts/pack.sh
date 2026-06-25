#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# pack.sh —— 把 Vite 工程打成 zip 排除 node_modules/dist/.git。
#
# 用法：
#   bash skills/web-video-presentation/scripts/pack.sh \
#       tmp/presentations/<id> \
#       output/<id>-source.zip
#
# 产出 zip 可发给用户，用户解压后 npm install && npm run dev 即可运行。
# ─────────────────────────────────────────────────────────────
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "用法: pack.sh <project-dir> <out-zip>" >&2
  echo "  project-dir: Vite 工程根目录（如 tmp/presentations/my-video）" >&2
  echo "  out-zip:     输出 zip 路径（如 output/my-video-source.zip）" >&2
  exit 1
fi

src="$1"
out="$2"

if [[ ! -d "$src" ]]; then
  echo "✗ 项目目录 '${src}' 不存在。" >&2
  exit 1
fi

# 确保输出目录存在
mkdir -p "$(dirname "$out")"

(cd "$(dirname "$src")" && zip -r "$OLDPWD/$out" "$(basename "$src")" \
  -x "*/node_modules/*" "*/dist/*" "*/.git/*")

echo "✓ 已打包: $out"
