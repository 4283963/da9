#!/bin/bash
# Git 仓库批量同步监视器 - 后端启动脚本

set -e

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "[INFO] 创建 Python 虚拟环境..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "[INFO] 安装 Python 依赖..."
pip install --upgrade pip > /dev/null
pip install -r requirements.txt

if [ ! -f "data/git_sync.db" ]; then
    echo "[INFO] 数据库不存在，先初始化 cc1 ~ cc10 仓库..."
    python init_repos.py
fi

HOST="${API_HOST:-0.0.0.0}"
PORT="${API_PORT:-8000}"

echo ""
echo "========================================="
echo "  Git Sync Monitor API 启动中..."
echo "  地址: http://${HOST}:${PORT}"
echo "  文档: http://localhost:${PORT}/docs"
echo "========================================="
echo ""

exec uvicorn app.main:app --host "${HOST}" --port "${PORT}" --reload
