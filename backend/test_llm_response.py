#!/usr/bin/env python3
"""
test_llm_response.py
====================
测试 LLM 响应是否正确，诊断空响应问题
"""

import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_qwen_matching():
    """测试 Qwen3-8b 匹配模型"""
    print("\n" + "="*60)
    print("🧪 测试 Qwen3-8b 匹配模型")
    print("="*60)
    
    api_key = os.getenv("BAIDU_API_KEY")
    if not api_key:
        print("❌ BAIDU_API_KEY 未设置")
        return False
    
    try:
        client = OpenAI(
            base_url='https://qianfan.baidubce.com/v2',
            api_key=api_key
        )
        
        prompt = """你是一个任务分类专家。根据以下模板列表判断这个指令属于哪个模板：
        
可用的模板：
- 1. notification: (通知|告诉|请)(.*?)到|来(.+?)(开会|会议|开个会|召集)
- 2. inspection: (巡视|巡检|检查|查看)(.+?)(并|拍照|照相|检查|检验)
- 3. transport: (运送|搬运|拿|送)(.+?)(到|去)(.+)

用户指令："通知张三和李四来2205开会"

请分析指令的语义，返回最匹配的模板名称。
只返回模板名称，不要其他内容。
如果没有匹配的模板，返回"none"。"""
        
        print(f"\n📝 发送请求到 Qwen3-8b...")
        response = client.chat.completions.create(
            model="qwen3-8b",
            messages=[
                {"role": "system", "content": "你是任务分类专家。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            top_p=0.8,
            extra_body={
                "penalty_score": 1,
                "stop": [],
                "enable_thinking": False
            }
        )
        
        print(f"\n✅ 收到响应")
        print(f"   响应对象: {type(response)}")
        print(f"   响应内容: {response}")
        
        if not response.choices:
            print(f"❌ 响应为空，choices 列表为空")
            return False
        
        choice = response.choices[0]
        print(f"\n   第一个 choice:")
        print(f"   - choice 对象: {type(choice)}")
        print(f"   - message 对象: {type(choice.message)}")
        print(f"   - content 值: {choice.message.content}")
        print(f"   - content 类型: {type(choice.message.content)}")
        
        if choice.message.content is None:
            print(f"❌ content 为 None！这是问题所在")
            print(f"   完整的 choice 对象: {choice}")
            print(f"   完整的 message 对象: {choice.message}")
            return False
        
        content = choice.message.content.strip()
        print(f"\n📋 处理后的内容: {content}")
        print(f"✅ Qwen3-8b 匹配模型工作正常!")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ernie_planning():
    """测试 Ernie-4.5 规划模型"""
    print("\n" + "="*60)
    print("🧪 测试 Ernie-4.5 规划模型")
    print("="*60)
    
    api_key = os.getenv("BAIDU_API_KEY")
    if not api_key:
        print("❌ BAIDU_API_KEY 未设置")
        return False
    
    try:
        client = OpenAI(
            base_url='https://qianfan.baidubce.com/v2',
            api_key=api_key
        )
        
        prompt = """请生成一个简单的 JSON 任务计划。

返回格式：
{
  "task": "测试任务",
  "status": "success"
}

只返回 JSON，不要其他内容。"""
        
        print(f"\n📝 发送请求到 Ernie-4.5...")
        response = client.chat.completions.create(
            model="ernie-4.5-21b-a3b-thinking",
            messages=[
                {"role": "system", "content": "你是任务规划专家。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            top_p=0.8,
            extra_body={
                "penalty_score": 1,
                "stop": [],
                "enable_thinking": True
            }
        )
        
        print(f"\n✅ 收到响应")
        print(f"   响应对象: {type(response)}")
        
        if not response.choices:
            print(f"❌ 响应为空，choices 列表为空")
            return False
        
        choice = response.choices[0]
        print(f"\n   第一个 choice:")
        print(f"   - content 值: {choice.message.content[:100]}...")
        print(f"   - content 类型: {type(choice.message.content)}")
        
        if choice.message.content is None:
            print(f"❌ content 为 None！")
            return False
        
        content = choice.message.content.strip()
        print(f"\n📋 成功获取规划响应")
        print(f"✅ Ernie-4.5 规划模型工作正常!")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*60)
    print("🔍 LLM 响应诊断工具")
    print("="*60)
    
    results = {
        "Qwen3-8b 匹配模型": test_qwen_matching(),
        "Ernie-4.5 规划模型": test_ernie_planning(),
    }
    
    print("\n" + "="*60)
    print("📊 诊断结果")
    print("="*60)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\n总体: {passed}/{total} 测试通过")
    
    if passed < total:
        print("\n💡 故障排查建议:")
        print("1. 检查 BAIDU_API_KEY 是否有效")
        print("2. 检查网络连接是否正常")
        print("3. 检查 API 配额是否充足")
        print("4. 检查模型名称是否正确 (qwen3-8b, ernie-4.5-21b-a3b-thinking)")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
