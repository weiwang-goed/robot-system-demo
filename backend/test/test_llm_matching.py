#!/usr/bin/env python3
"""
test_llm_matching.py
===================
测试 LLM 驱动的模板匹配和参数提取

功能：
- 测试 LLM 模板匹配
- 验证参数提取
- 测试完整的任务规划流程
"""

import json
import sys
from pathlib import Path

# 添加 backend 目录到 Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm_planner_baidu import BaiduPlanner
from task_templates_core import get_template_engine


def test_template_matching():
    """测试 LLM 模板匹配"""
    print("\n" + "="*60)
    print("测试 1: LLM 模板匹配和参数提取")
    print("="*60)
    
    try:
        engine = get_template_engine()
        
        test_cases = [
            "通知李涛和吴晋来2215开会",
            "巡视一楼并拍照检查",
            "把物料运送到仓库",
            "查询2215会议室的会议时间"
        ]
        
        for instruction in test_cases:
            print(f"\n指令: {instruction}")
            result = engine.apply_template(instruction)
            
            if result:
                print(f"  匹配模板: {result.get('template_name')}")
                print(f"  置信度: {result.get('confidence', 0):.2f}")
                print(f"  是否匹配: {result.get('matched')}")
                print(f"  提取参数: {json.dumps(result.get('params', {}), ensure_ascii=False, indent=2)}")
            else:
                print("  模板匹配失败")
    
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


def test_full_planning():
    """测试完整的任务规划流程"""
    print("\n" + "="*60)
    print("测试 2: 完整的任务规划流程")
    print("="*60)
    
    try:
        planner = BaiduPlanner()
        
        test_instruction = "通知王明和李强到5楼会议室开营销会议"
        test_robots = [
            {"id": "QR-SZZX-0001", "name": "通知机器人", "status": "ONLINE"},
            {"id": "QR-XJJG-0001", "name": "巡检机器人", "status": "ONLINE"},
            {"id": "QR-YSXR-0001", "name": "运送机器人", "status": "ONLINE"}
        ]
        
        print(f"\n指令: {test_instruction}")
        
        # 分析意图
        print("\n步骤 1: 分析意图...")
        intent = planner.analyze_intent(test_instruction, test_robots)
        print(f"  意图类型: {intent.intent_type}")
        print(f"  主要动作: {intent.primary_action}")
        print(f"  描述: {intent.description}")
        print(f"  置信度: {intent.confidence:.2f}")
        print(f"  提取的参数: {json.dumps(intent.parameters, ensure_ascii=False, indent=2)}")
        
        # 生成任务计划
        print("\n步骤 2: 生成任务计划...")
        plan = planner.generate_task_plan(test_instruction, intent, test_robots)
        
        print(f"\n规划结果:")
        print(f"  Run ID: {plan.get('run_id')}")
        print(f"  模型: {plan.get('model')}")
        print(f"  使用的模板: {plan.get('template_used', 'N/A')}")
        
        if plan.get('template_confidence'):
            print(f"  模板置信度: {plan.get('template_confidence'):.2f}")
        
        params = plan.get('params', {})
        if params:
            print(f"  提取的参数:")
            print(f"    {json.dumps(params, ensure_ascii=False, indent=4)}")
        
        llm_params = plan.get('parameters', {})
        if llm_params:
            print(f"  LLM 提取的参数:")
            print(f"    {json.dumps(llm_params, ensure_ascii=False, indent=4)}")
        
        global_planning = plan.get('llm_global_planning', [])
        if global_planning:
            print(f"  全局规划 ({len(global_planning)} 个任务):")
            for task in global_planning:
                print(f"    - 任务 {task.get('task_order')}: {task.get('task')}")
                print(f"      描述: {task.get('description')}")
        
        tool_calls = plan.get('robot_tool_calls', {})
        if tool_calls:
            print(f"  机器人动作:")
            for robot_id, actions in tool_calls.items():
                print(f"    {robot_id}:")
                for action in actions:
                    print(f"      - {action.get('action')}: {action.get('arguments')}")
        
        constraints = plan.get('constraints', [])
        if constraints:
            print(f"  约束条件:")
            for constraint in constraints:
                print(f"    - {constraint}")
        
        print("\n✓ 测试完成!")
    
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("LLM 驱动的模板匹配和参数提取 - 完整测试")
    print("="*60)
    
    print("\n注意: 此测试需要 BAIDU_API_KEY 环境变量")
    
    test_template_matching()
    test_full_planning()
    
    print("\n" + "="*60)
    print("所有测试完成！")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
