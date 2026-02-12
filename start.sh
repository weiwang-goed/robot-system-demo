#!/bin/bash
# start.sh - 一键启动 Node.js + FastAPI

echo "=== Robot Console Dashboard (Unified Port 7000) ===" 

# 定义虚拟环境路径
VENV_PATH="/home/svr/rb-sys-demo/robot-system-demo/.venv"
PYTHON_EXE="${VENV_PATH}/bin/python3"

# 检查并创建虚拟环境（仅修复语法错误）
if [ ! -f "$PYTHON_EXE" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv "$VENV_PATH"
fi

# 激活虚拟环境（核心新增逻辑）
echo "Activating virtual environment..."
source "${VENV_PATH}/bin/activate"

# 启动 FastAPI（后台，激活虚拟环境后运行）
echo "Starting FastAPI backend on port 7000..."
uvicorn backend.app:app --host 127.0.0.1 --port 7000 &  # 激活后可直接用uvicorn，无需完整Python路径
FASTAPI_PID=$!
echo "FastAPI PID: $FASTAPI_PID"

# 等待 FastAPI 启动
sleep 2

# 启动 Node.js（前台，便于观察日志）
echo "Starting Node.js server on port 7000..."
echo "Open http://localhost:7000 in your browser"
echo "" 

node server.js

# 清理：用户关闭 Node.js 时停止 FastAPI
echo "Stopping FastAPI backend..."
kill $FASTAPI_PID 2>/DEV/NULL
# 退出虚拟环境（可选，脚本结束后自动退出）
deactivate
echo "Done."
