#!/bin/bash
# Git 仓库批量同步监视器 - 前端启动脚本

set -e

cd "$(dirname "$0")"

if [ ! -d "node_modules" ]; then
    echo "[INFO] 安装 npm 依赖..."
    npm install
fi

echo ""
echo "========================================="
echo "  Git Sync Monitor 前端启动中..."
echo "  地址: http://localhost:5173"
echo "  后端代理: http://localhost:8000"
echo "========================================="
echo ""

exec npm run dev
