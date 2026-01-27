#!/usr/bin/env python3
"""
测试脚本：验证 /api/generate_plan 端点的完整流程
"""

import requests
import json
import sys
from pathlib import Path

# 配置
FASTAPI_URL = "http://127.0.0.1:8000"
NODE_URL = "http://127.0.0.1:3000"

def test_fastapi_direct():
    """直接测试 FastAPI 后端"""
    print("\n" + "="*60)
    print("测试 1: 直接调用 FastAPI 后端")
    print("="*60)
    
    payload = {
        "instruction": "巡视一区进行视频拍摄",
        "site": "一区"
    }
    
    print(f"\n请求 URL: {FASTAPI_URL}/api/generate_plan")
    print(f"请求体: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    
    try:
        response = requests.post(
            f"{FASTAPI_URL}/api/generate_plan",
            json=payload,
            timeout=30
        )
        print(f"\n响应状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ 收到 JSON 响应")
            print(f"响应类型: {type(data)}")
            print(f"顶级键: {list(data.keys())}")
            
            # 检查是否包含预期的字段
            if 'llm_global_planning' in data:
                print(f"✓ 包含 llm_global_planning (长度: {len(data['llm_global_planning'])})")
            else:
                print(f"✗ 缺少 llm_global_planning")
            
            if 'robot_tool_calls' in data:
                print(f"✓ 包含 robot_tool_calls (键: {list(data['robot_tool_calls'].keys())})")
            else:
                print(f"✗ 缺少 robot_tool_calls")
            
            # 保存响应到文件便于查看
            with open('/tmp/fastapi_response.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"\n完整响应已保存到: /tmp/fastapi_response.json")
            
            return True
        else:
            print(f"\n✗ 错误响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n✗ 请求失败: {e}")
        return False


def test_node_proxy():
    """通过 Node 代理测试"""
    print("\n" + "="*60)
    print("测试 2: 通过 Node 代理调用")
    print("="*60)
    
    payload = {
        "instruction": "巡视一区进行视频拍摄",
        "site": "一区"
    }
    
    print(f"\n请求 URL: {NODE_URL}/api/generate_plan")
    print(f"请求体: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    
    try:
        response = requests.post(
            f"{NODE_URL}/api/generate_plan",
            json=payload,
            timeout=30
        )
        print(f"\n响应状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ 收到 JSON 响应")
            print(f"响应类型: {type(data)}")
            print(f"顶级键: {list(data.keys())}")
            
            # 检查是否包含预期的字段
            if 'llm_global_planning' in data:
                print(f"✓ 包含 llm_global_planning (长度: {len(data['llm_global_planning'])})")
            else:
                print(f"✗ 缺少 llm_global_planning")
            
            if 'robot_tool_calls' in data:
                print(f"✓ 包含 robot_tool_calls (键: {list(data['robot_tool_calls'].keys())})")
            else:
                print(f"✗ 缺少 robot_tool_calls")
            
            return True
        else:
            print(f"\n✗ 错误响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n✗ 请求失败: {e}")
        return False


def check_demo_run():
    """检查 demo_run.json 的内容"""
    print("\n" + "="*60)
    print("测试 3: 检查 demo_run.json 内容")
    print("="*60)
    
    demo_path = Path(__file__).parent / "data" / "demo_run.json"
    
    if not demo_path.exists():
        print(f"\n✗ 文件不存在: {demo_path}")
        return False
    
    try:
        with open(demo_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n✓ 文件存在: {demo_path}")
        print(f"文件大小: {demo_path.stat().st_size} bytes")
        print(f"顶级键: {list(data.keys())}")
        
        if 'llm_global_planning' in data:
            print(f"✓ 包含 llm_global_planning (长度: {len(data['llm_global_planning'])})")
        else:
            print(f"✗ 缺少 llm_global_planning")
        
        if 'robot_tool_calls' in data:
            print(f"✓ 包含 robot_tool_calls")
        else:
            print(f"✗ 缺少 robot_tool_calls")
        
        if 'llm_thinking' in data:
            print(f"✓ 包含 llm_thinking")
            thinking = data['llm_thinking']
            if isinstance(thinking, str):
                print(f"  长度: {len(thinking)} chars")
        else:
            print(f"ℹ 没有 llm_thinking 字段")
        
        return True
        
    except Exception as e:
        print(f"\n✗ 读取失败: {e}")
        return False


if __name__ == "__main__":
    print("\n🔍 开始诊断 /api/generate_plan 端点\n")
    
    # 测试 FastAPI 后端
    fastapi_ok = test_fastapi_direct()
    
    # 测试 Node 代理
    node_ok = test_node_proxy()
    
    # 检查 demo_run.json
    demo_ok = check_demo_run()
    
    # 总结
    print("\n" + "="*60)
    print("诊断总结")
    print("="*60)
    print(f"FastAPI 后端:  {'✓ OK' if fastapi_ok else '✗ FAIL'}")
    print(f"Node 代理:     {'✓ OK' if node_ok else '✗ FAIL'}")
    print(f"demo_run.json: {'✓ OK' if demo_ok else '✗ FAIL'}")
    
    if fastapi_ok and node_ok:
        print("\n✓ 前后端连接正常，应该可以显示结果")
    elif fastapi_ok and not node_ok:
        print("\n✗ FastAPI 正常但 Node 代理有问题")
    elif not fastapi_ok:
        print("\n✗ FastAPI 后端有问题")
    
    sys.exit(0 if fastapi_ok else 1)
