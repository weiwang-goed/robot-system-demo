#!/usr/bin/env python3
"""
后端服务启动脚本
可通过命令行指定端口，默认 8000
"""
import sys
import subprocess
from pathlib import Path

port = sys.argv[1] if len(sys.argv) > 1 else "8000"
host = "0.0.0.0"

project_root = Path(__file__).resolve().parent
print(f"启动后端服务...")
print(f"地址: http://{host}:{port}")
print(f"确保前端静态服务也在运行（通常 http://localhost:8001）")
print()

cmd = [
    sys.executable, "-m", "uvicorn",
    "backend.app:app",
    "--host", host,
    "--port", port
]

subprocess.run(cmd, cwd=str(project_root))
