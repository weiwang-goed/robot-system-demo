#!/usr/bin/env python3
"""run_baidu_demo.py
Consolidated demo and test runner for Baidu Qianfan planner.

This script loads the backend/.env automatically (if present) so BAIDU_API_KEY
and BAIDU_MODEL are available to the planner. It runs a small suite of
interactive/integration tests that used to live in separate test_baidu_*.py
files.

Usage:
    python run_baidu_demo.py
"""
import os
import sys
import json
from pathlib import Path

from dotenv import load_dotenv

# Ensure backend/.env is loaded if present
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

from llm_planner_baidu import create_planner


def load_robots():
    """Load robots data from data/robots.json or return demo data."""
    robots_file = Path(__file__).parent.parent / "data" / "robots.json"
    if not robots_file.exists():
        return [
            {
                "id": "WR-GYL-0001",
                "type": "wheel_robot",
                "category": "轮式机器人",
                "status": "online",
                "battery": 85,
                "location": "warehouse",
                "capabilities": ["navigate", "sense"]
            },
            {
                "id": "QZ-JT-0002",
                "type": "quadruped_robot",
                "category": "四足机器人",
                "status": "online",
                "battery": 72,
                "location": "warehouse",
                "capabilities": ["navigate", "manipulate", "sense"]
            },
            {
                "id": "WJ-UT-0003",
                "type": "drone",
                "category": "无人机",
                "status": "online",
                "battery": 60,
                "location": "office",
                "capabilities": ["navigate", "sense", "communicate"]
            }
        ]

    with open(robots_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def print_section(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_query():
    print_section("测试 1: 查询功能")
    try:
        planner = create_planner()
        robots = load_robots()

        query = "系统中有多少台机器人？它们现在的状态如何？"
        print(f"\n用户查询: {query}")

        intent = planner.analyze_intent(query, robots)
        print(f"✓ 意图类型: {intent.intent_type}")
        print(f"  主要动作: {intent.primary_action}")
        print(f"  描述: {intent.description}")
        print(f"  置信度: {intent.confidence}")

        if intent.intent_type == "query":
            response = planner.generate_query_response(query, robots)
            print(f"✓ 状态: {response.get('status')}")
            print(f"\n回答:\n{response.get('answer')}")
            return True
        else:
            print(f"✗ 意图分类错误: 应该是 'query'，但得到 '{intent.intent_type}'")
            return False

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_task_planning():
    print_section("测试 2: 任务规划功能")
    try:
        planner = create_planner()
        robots = load_robots()

        instruction = "将仓库中的货物搬运到办公室"
        print(f"\n用户指令: {instruction}")

        intent = planner.analyze_intent(instruction, robots)
        print(f"✓ 意图类型: {intent.intent_type}")
        print(f"  主要动作: {intent.primary_action}")
        print(f"  描述: {intent.description}")
        print(f"  置信度: {intent.confidence}")

        if intent.intent_type == "task":
            plan = planner.generate_task_plan(instruction, intent, robots)

            print(f"✓ 任务 ID: {plan.get('run_id')}")
            print(f"  状态: {plan.get('status')}")
            print(f"  任务类型: {plan.get('task_type')}")
            print(f"  模型: {plan.get('model')}")

            if 'llm_thinking' in plan:
                print(f"\n  LLM 思考过程:\n{plan.get('llm_thinking')}")

            if 'llm_global_planning' in plan:
                print(f"\n  全局规划:")
                for task in plan.get('llm_global_planning', [])[:10]:
                    print(f"    - [{task.get('task_order', 0)}] {task.get('robot_id', 'N/A')}: {task.get('task', 'N/A')}")

            if 'robot_tool_calls' in plan:
                print(f"\n  机器人动作序列:")
                for robot_id, actions in plan.get('robot_tool_calls', {}).items():
                    print(f"    {robot_id}:")
                    for i, action in enumerate(actions[:10], 1):
                        print(f"      {i}. {action.get('action', 'N/A')}")
                        print(f"         参数: {action.get('arguments', 'N/A')}")

            if 'constraints' in plan:
                print(f"\n  执行约束:")
                for constraint in plan.get('constraints', [])[:10]:
                    print(f"    - {constraint}")

            print(f"\n  预计耗时: {plan.get('estimated_duration_ms', 0)}ms")
            return True
        else:
            print(f"✗ 意图分类错误: 应该是 'task'，但得到 '{intent.intent_type}'")
            return False

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_complex_planning():
    print_section("测试 3: 复杂多步骤规划")
    try:
        planner = create_planner()
        robots = load_robots()

        instruction = "对仓库进行全面巡检，检查所有货架，然后将有问题的货物标记出来"
        print(f"\n用户指令: {instruction}")

        intent = planner.analyze_intent(instruction, robots)
        print(f"✓ 意图类型: {intent.intent_type}")
        print(f"  主要动作: {intent.primary_action}")

        if intent.intent_type == "task":
            plan = planner.generate_task_plan(instruction, intent, robots, site="warehouse")
            print(f"✓ 任务 ID: {plan.get('run_id')}")

            if 'llm_thinking' in plan:
                thinking = plan.get('llm_thinking', '')
                if len(thinking) > 500:
                    print(f"{thinking[:500]}...\n[过长，省略部分内容]")
                else:
                    print(thinking)

            if 'llm_global_planning' in plan:
                print(f"\n  全局任务分解:")
                for task in plan.get('llm_global_planning', [])[:20]:
                    print(f"    - {task.get('robot_id', 'N/A')}: {task.get('task', 'N/A')}")

            return True
        else:
            print(f"✗ 意图分类错误")
            return False

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_handling():
    print_section("测试 4: 错误处理")
    try:
        planner = create_planner()
        robots = load_robots()

        print("\n[1] 测试空指令...")
        intent = planner.analyze_intent("", robots)
        print(f"✓ 返回默认意图: {intent.intent_type}")

        print("\n[2] 测试歧义指令...")
        ambiguous = "嗯"
        intent = planner.analyze_intent(ambiguous, robots)
        print(f"✓ 置信度: {intent.confidence}")

        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def run_all_tests():
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  🤖 百度千帆 LLM Planner 测试套件".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")

    results = {
        "查询功能": test_query(),
        "任务规划": test_task_planning(),
        "复杂规划": test_complex_planning(),
        "错误处理": test_error_handling()
    }

    print_section("测试总结")
    print("\n测试结果:")
    passed = 0
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")
        if result:
            passed += 1

    print(f"\n总计: {passed}/{len(results)} 测试通过")

    if passed == len(results):
        print("\n🎉 所有测试都通过了！")
    else:
        print(f"\n⚠️  有 {len(results) - passed} 个测试失败")

    return passed == len(results)


if __name__ == "__main__":
    # Ensure API key is available (from backend/.env or environment)
    api_key = os.getenv("BAIDU_API_KEY")
    if not api_key:
        print("\n❌ 错误: BAIDU_API_KEY 未在环境或 backend/.env 中设置")
        print(f"查找的 .env 路径: {env_path}")
        print("请在该文件中设置 BAIDU_API_KEY 或导出到环境变量，然后重新运行。")
        sys.exit(1)

    success = run_all_tests()
    sys.exit(0 if success else 1)
