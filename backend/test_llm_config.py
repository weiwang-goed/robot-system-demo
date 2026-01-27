#!/usr/bin/env python3
"""
test_llm_config.py
==================
测试 LLM 配置和 Template 匹配系统

用法:
    python test_llm_config.py
"""

import json
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from task_templates_core import get_template_engine
from llm_planner_baidu import BaiduPlanner

def test_env_variables():
    """测试环境变量配置"""
    print("\n" + "="*60)
    print("🔍 检查环境变量配置")
    print("="*60)
    
    required_vars = {
        "PLANNER_TYPE": "planner类型",
        "BAIDU_API_KEY": "百度API密钥",
        "MATCHING_MODEL": "意图识别模型",
        "PLANNING_MODEL": "规划模型",
    }
    
    all_ok = True
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            # 隐藏敏感信息
            if "KEY" in var:
                display = value[:10] + "****" + value[-5:]
            else:
                display = value
            print(f"✅ {var}: {display}")
        else:
            print(f"❌ {var}: 未设置 ({desc})")
            all_ok = False
    
    optional_vars = {
        "MATCHING_TEMPERATURE": "0.7",
        "MATCHING_TOP_P": "0.8",
        "PLANNING_TEMPERATURE": "0.3",
        "PLANNING_TOP_P": "0.8",
        "MATCHING_ENABLE_THINKING": "false",
        "PLANNING_ENABLE_THINKING": "true",
    }
    
    print("\n可选配置:")
    for var, default in optional_vars.items():
        value = os.getenv(var, default)
        print(f"  {var}: {value}")
    
    return all_ok

def test_template_engine():
    """测试 Template 引擎"""
    print("\n" + "="*60)
    print("🎯 测试 Template 引擎")
    print("="*60)
    
    try:
        engine = get_template_engine()
        print("✅ Template 引擎初始化成功")
        print(f"   已加载 {len(engine.template_specs)} 个模板")

        for spec in engine.template_specs:
            print(f"   - {spec.name} (优先级: {spec.priority})")
        
        return True
    except Exception as e:
        print(f"❌ Template 引擎初始化失败: {e}")
        return False

def test_llm_matching():
    """测试 LLM 匹配"""
    print("\n" + "="*60)
    print("🤖 测试 LLM 匹配")
    print("="*60)
    
    try:
        engine = get_template_engine()

        if not engine.client:
            print("⚠️  LLM 客户端未初始化，跳过 LLM 匹配测试")
            return True
        
        print(f"✅ LLM 客户端已初始化")
        print(f"   使用模型: {engine.matching_model}")
        
        test_instruction = "请通知王经理和张主管到2215开个会"
        print(f"\n测试指令: {test_instruction}")
        
        result = engine.apply_template(test_instruction)
        if result and result.get("matched"):
            print(f"✅ LLM 匹配成功: {result.get('template_name')}")
            print(f"   置信度: {result.get('confidence', 0):.2f}")
            print(f"   参数: {json.dumps(result.get('params', {}), ensure_ascii=False)}")
        else:
            print("⚠️  LLM 未匹配到模板")
        
        return True
    except Exception as e:
        print(f"❌ LLM 匹配测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_planner_initialization():
    """测试 Planner 初始化"""
    print("\n" + "="*60)
    print("🚀 测试 Planner 初始化")
    print("="*60)
    
    try:
        planner = BaiduPlanner()
        print(f"✅ BaiduPlanner 初始化成功")
        print(f"   规划模型: {planner.planning_model}")
        print(f"   匹配模型: {planner.template_engine.matching_model}")
        print(f"   规划温度: {planner.planning_temperature}")
        print(f"   规划 TopP: {planner.planning_top_p}")
        print(f"   启用思维链: {planner.planning_enable_thinking}")
        
        return True
    except Exception as e:
        print(f"❌ Planner 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试流程"""
    print("\n" + "="*60)
    print("📊 LLM 配置系统测试")
    print("="*60)
    
    results = {
        "环境变量": test_env_variables(),
        "Template引擎": test_template_engine(),
        "LLM匹配": test_llm_matching(),
        "Planner初始化": test_planner_initialization(),
    }
    
    print("\n" + "="*60)
    print("📈 测试摘要")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n总体: {passed}/{total} 测试通过")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
