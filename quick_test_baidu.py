#!/usr/bin/env python3
"""
quick_test_baidu.py
===================
快速测试百度千帆规划功能

使用方式：
    export BAIDU_API_KEY="bce-v3/..."
    python quick_test_baidu.py
"""

import os
import sys
from pathlib import Path

# 添加 backend 路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

def test_baidu_integration():
    """测试百度千帆集成"""
    print("\n" + "="*70)
    print("  🤖 百度千帆规划系统快速测试")
    print("="*70)
    
    # 1. 检查 API 密钥
    print("\n[1] 检查环境配置...")
    api_key = os.getenv("BAIDU_API_KEY")
    if not api_key:
        print("❌ BAIDU_API_KEY 未设置")
        print("\n设置方法:")
        print("  export BAIDU_API_KEY='bce-v3/ALTAK-FIyM1bJHsGEYqMv6Ub6rI/...'")
        return False
    
    print(f"✓ API 密钥已设置: {api_key[:30]}...")
    
    # 2. 导入规划器
    print("\n[2] 导入规划器...")
    try:
        from llm_planner_baidu import create_planner
        print("✓ 规划器导入成功")
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False
    
    # 3. 初始化规划器
    print("\n[3] 初始化规划器...")
    try:
        planner = create_planner(api_key=api_key)
        print("✓ 规划器初始化成功")
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return False
    
    # 4. 准备测试数据
    print("\n[4] 准备测试数据...")
    test_robots = [
        {
            "id": "WR-GYL-0001",
            "type": "wheel_robot",
            "category": "轮式机器人",
            "status": "online",
            "battery": 85,
            "location": "warehouse"
        },
        {
            "id": "QZ-JT-0002",
            "type": "quadruped_robot",
            "category": "四足机器人",
            "status": "online",
            "battery": 72,
            "location": "warehouse"
        },
        {
            "id": "WJ-UT-0003",
            "type": "drone",
            "category": "无人机",
            "status": "online",
            "battery": 60,
            "location": "office"
        }
    ]
    print(f"✓ 已加载 {len(test_robots)} 台机器人")
    
    # 5. 测试查询
    print("\n[5] 测试查询功能...")
    print("   指令: '系统中有多少台机器人？'")
    try:
        query = "系统中有多少台机器人？"
        intent = planner.analyze_intent(query, test_robots)
        
        print(f"   ✓ 意图分析:")
        print(f"     - 类型: {intent.intent_type}")
        print(f"     - 主要动作: {intent.primary_action}")
        print(f"     - 置信度: {intent.confidence:.2f}")
        
        if intent.intent_type == "query":
            response = planner.generate_query_response(query, test_robots)
            print(f"\n   ✓ AI 回答:")
            answer = response.get('answer', '')
            # 显示前 300 个字符
            if len(answer) > 300:
                print(f"     {answer[:300]}...\n     [回答过长，省略部分内容]")
            else:
                print(f"     {answer}")
        else:
            print(f"   ⚠️  意图类型应该是 'query'，但返回 '{intent.intent_type}'")
    
    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 6. 测试任务规划
    print("\n[6] 测试任务规划功能...")
    print("   指令: '将货物从仓库搬运到办公室'")
    try:
        instruction = "将货物从仓库搬运到办公室"
        intent = planner.analyze_intent(instruction, test_robots)
        
        print(f"   ✓ 意图分析:")
        print(f"     - 类型: {intent.intent_type}")
        print(f"     - 主要动作: {intent.primary_action}")
        print(f"     - 置信度: {intent.confidence:.2f}")
        
        if intent.intent_type == "task":
            plan = planner.generate_task_plan(instruction, intent, test_robots)
            
            print(f"\n   ✓ 任务规划:")
            print(f"     - 任务 ID: {plan['run_id']}")
            print(f"     - 状态: {plan['status']}")
            print(f"     - 模型: {plan['model']}")
            
            # 显示选择的机器人
            if 'robot_tool_calls' in plan:
                robots_selected = list(plan['robot_tool_calls'].keys())
                print(f"     - 选择的机器人: {', '.join(robots_selected)}")
                
                # 显示动作序列
                for robot_id, actions in plan['robot_tool_calls'].items():
                    print(f"\n     {robot_id} 的动作序列:")
                    for i, action in enumerate(actions[:5], 1):  # 只显示前 5 个动作
                        print(f"       {i}. {action.get('action', 'N/A')}: {action.get('arguments', 'N/A')}")
                    if len(actions) > 5:
                        print(f"       ... 还有 {len(actions) - 5} 个动作")
        else:
            print(f"   ⚠️  意图类型应该是 'task'，但返回 '{intent.intent_type}'")
    
    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 7. 测试 FastAPI 集成
    print("\n[7] 测试 FastAPI 集成...")
    print("   检查 app.py 是否能正确加载规划器...")
    try:
        from app import planner as app_planner, PLANNER_NAME
        print(f"   ✓ FastAPI 已加载规划器: {PLANNER_NAME}")
    except Exception as e:
        print(f"   ⚠️  警告: {e}")
    
    # 完成
    print("\n" + "="*70)
    print("  ✅ 所有测试完成！百度千帆集成成功")
    print("="*70)
    
    print("\n📝 接下来的步骤:")
    print("   1. 启动 FastAPI 服务:")
    print("      export PLANNER_TYPE=baidu")
    print("      export BAIDU_API_KEY='...'")
    print("      python -m uvicorn backend.app:app --reload --port 9000")
    print("\n   2. 在另一个终端测试 API:")
    print("      curl -X POST http://localhost:9000/api/generate_plan \\")
    print("        -H 'Content-Type: application/json' \\")
    print("        -d '{\"instruction\": \"将货物搬到办公室\"}'")
    
    return True


if __name__ == "__main__":
    success = test_baidu_integration()
    sys.exit(0 if success else 1)
