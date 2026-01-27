#!/usr/bin/env python3
"""
debug_planning.py
=================
调试规划生成时的 NoneType 错误
"""

import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from llm_planner_baidu import BaiduPlanner, IntentAnalysis


def test_template_matching():
    """测试模板匹配"""
    print("\n" + "="*60)
    print("🎯 测试模板匹配")
    print("="*60)
    
    try:
        planner = BaiduPlanner()
        
        test_instruction = "通知张三，李涛来2201开会"
        print(f"\n测试指令: {test_instruction}")
        
        # 测试模板匹配
        template_result = planner.template_engine.apply_template(test_instruction)
        
        if template_result:
            print(f"✅ 模板匹配成功: {template_result['template_name']}")
            print(f"   参数: {template_result['params']}")
            print(f"   工具调用: {json.dumps(template_result['robot_tool_calls'], ensure_ascii=False, indent=2)[:200]}")
        else:
            print(f"❌ 模板匹配失败")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_planning_generation():
    """测试规划生成"""
    print("\n" + "="*60)
    print("📋 测试规划生成")
    print("="*60)
    
    try:
        planner = BaiduPlanner()
        
        instruction = "通知张三，李涛来2201开会"
        
        # 创建意图分析对象
        intent = IntentAnalysis(
            intent_type="task",
            confidence=0.95,
            primary_action="notification",
            description="通知多人参加会议",
            requires_robots=True,
            estimated_duration_ms=5000,
            parameters={"recipients": ["张三", "李涛"], "location": "2201"}
        )
        
        # 获取机器人列表
        robots = [
            {
                "id": "QR-SZZX-0001",
                "name": "通知机器人",
                "capabilities": ["speech_synthesis", "navigation", "search_person"]
            }
        ]
        
        print(f"\n测试指令: {instruction}")
        print(f"意图类型: {intent.primary_action}")
        print(f"可用机器人: {robots}")
        
        # 生成任务计划
        print(f"\n📝 调用 generate_task_plan...")
        result = planner.generate_task_plan(
            instruction=instruction,
            intent=intent,
            robots=robots,
            site=None
        )
        
        print(f"\n✅ 规划生成成功!")
        print(f"   状态: {result.get('status')}")
        print(f"   模型: {result.get('model')}")
        print(f"   模板: {result.get('template_used', 'N/A')}")
        
        if result.get('status') == 'ERROR':
            print(f"   错误: {result.get('error')}")
            return False
        
        # 显示规划数据
        if 'llm_global_planning' in result:
            print(f"   全局规划: {json.dumps(result['llm_global_planning'], ensure_ascii=False)[:200]}")
        
        if 'robot_tool_calls' in result:
            print(f"   机器人工具调用: {json.dumps(result['robot_tool_calls'], ensure_ascii=False)[:200]}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*60)
    print("🔍 规划生成调试工具")
    print("="*60)
    
    results = {
        "模板匹配": test_template_matching(),
        "规划生成": test_planning_generation(),
    }
    
    print("\n" + "="*60)
    print("📊 测试结果")
    print("="*60)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\n总体: {passed}/{total} 测试通过")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
