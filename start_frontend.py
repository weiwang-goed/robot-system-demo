#!/usr/bin/env python3
"""
前端静态服务启动脚本
默认 7001 端口
"""
import sys
import subprocess
from pathlib import Path

port = sys.argv[1] if len(sys.argv) > 1 else "7001"

project_root = Path(__file__).resolve().parent
print(f"启动前端静态服务...")
print(f"地址: http://localhost:{port}/index.html")
print()

cmd = [
    sys.executable, "-m", "http.server",
    port,
    "--directory", str(project_root)
]

subprocess.run(cmd)
