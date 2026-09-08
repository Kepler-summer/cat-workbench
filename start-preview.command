#!/bin/bash
# 二猫工作台 · 本地实时预览（双击运行）
# 常驻说明：此窗口开着，服务就在；关闭窗口即停止。
# - 改动保存后 1 秒内自动刷新，不用手动 Cmd+R
# - 监听 0.0.0.0，同一 Wi-Fi 的手机也能打开（地址启动时会在窗口里打印）
# - 已禁用缓存（no-store）
cd "$(dirname "$0")" || exit 1

PORT=8766
# 端口被占用则顺延，避免"启动没反应"
while lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; do
  PORT=$((PORT+1))
done
export PREVIEW_PORT=$PORT

if ! command -v python3 >/dev/null 2>&1; then
  echo "未找到 python3，请先安装。"
  exit 1
fi

echo ""
exec python3 preview-server.py
