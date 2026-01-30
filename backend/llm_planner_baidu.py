"""
llm_planner_baidu.py
===================
使用百度千帆 API 的 LLM Planner

Features:
- 调用百度千帆 ERNIE 模型进行意图识别和任务规划
- 真正对接 robot_behaviors_schema.json
- 生成智能的机器人任务计划
- 支持多步骤任务流程
- 思维链（Chain of Thought）增强推理能力

环境变量：
- BAIDU_API_KEY: 百度千帆 API 密钥
- BAIDU_MODEL: 使用的模型（默认：ernie-4.5-21b-a3b-thinking）

API 文档：https://cloud.baidu.com/doc/ERNIE-Speed/s/Fmzr2uq8o
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
import logging
import re

from dotenv import load_dotenv
from openai import OpenAI
from task_templates_core import get_template_engine
from execution_supervisor import SupervisedExecutor

logger = logging.getLogger(__name__)

# 尝试从同目录下加载 .env 文件（backend/.env）以便读取 BAIDU_API_KEY
try:
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        logging.getLogger(__name__).info(f"Loaded env from {env_path}")
    else:
        # 不强制，可能用户使用系统环境变量
        logging.getLogger(__name__).debug(f"No .env found at {env_path}")
except Exception:
    logging.getLogger(__name__).warning("Failed to load .env file")


@dataclass
class IntentAnalysis:
    """意图分析结果"""
    intent_type: str  # "query" 或 "task"
    confidence: float
    primary_action: str
    description: str
    requires_robots: bool
    estimated_duration_ms: int
    parameters: Dict[str, Any] = None  # 额外参数（如地点、对象等）

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


class BaiduPlanner:
    """
    基于百度千帆的机器人规划器
    
    使用 ERNIE 模型的思维链能力进行高质量推理
    """

    def __init__(self, schema_path: Optional[Path] = None, api_key: Optional[str] = None):
        """
        初始化百度千帆规划器
        
        Args:
            schema_path: robot_behaviors_schema.json 路径
            api_key: 百度千帆 API Key（如果不提供则从环境变量读取）
        """
        if schema_path is None:
            schema_path = Path(__file__).resolve().parent.parent / "data" / "robot_behaviors_schema.json"
        
        self.schema_path = schema_path
        self.schema = self._load_schema()
        
        # 初始化百度千帆客户端
        api_key = api_key or os.getenv("BAIDU_API_KEY")
        if not api_key:
            raise ValueError(
                "BAIDU_API_KEY 环境变量未设置。"
                "请设置: export BAIDU_API_KEY='your-key' 或在代码中传入 api_key"
            )
        
        self.client = OpenAI(
            base_url='https://qianfan.baidubce.com/v2',
            api_key=api_key
        )
        
        # 意图识别模型配置（Qwen-8b 轻量级）
        self.intent_model = os.getenv("INTENT_MODEL", "qwen3-8b")
        self.intent_temperature = float(os.getenv("INTENT_TEMPERATURE", "0.3"))
        self.intent_top_p = float(os.getenv("INTENT_TOP_P", "0.8"))
        self.intent_penalty_score = float(os.getenv("INTENT_PENALTY_SCORE", "1"))
        
        # 规划用的模型配置（高性能模型用于复杂规划）
        self.planning_model = os.getenv("PLANNING_MODEL", "ernie-4.5-21b-a3b-thinking")
        self.planning_temperature = float(os.getenv("PLANNING_TEMPERATURE", "0.3"))
        self.planning_top_p = float(os.getenv("PLANNING_TOP_P", "0.8"))
        self.planning_penalty_score = float(os.getenv("PLANNING_PENALTY_SCORE", "1"))
        self.planning_enable_thinking = os.getenv("PLANNING_ENABLE_THINKING", "true").lower() == "true"
        
        self.template_engine = get_template_engine()
        self.executor = SupervisedExecutor(template_engine=self.template_engine)
        
        logger.info("初始化百度千帆 Planner，已集成任务模板系统")
        logger.info(f"意图识别模型: {self.intent_model}")
        logger.info(f"规划模型: {self.planning_model}")

    def _load_schema(self) -> Dict[str, Any]:
        """加载机器人行为 schema"""
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema 文件不存在: {self.schema_path}")
        
        with open(self.schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        
        logger.info(f"已加载 Schema: {self.schema_path}")
        return schema

    def _get_schema_prompt(self) -> str:
        """生成包含 schema 信息的提示词"""
        schema = self.schema
        prompt = "# 可用的机器人及其能力\n\n"
        
        # 添加机器人类型和能力
        for robot_type, robot_info in schema.get("robot_behaviors", {}).items():
            prompt += f"## {robot_info.get('category', robot_type)}\n"
            prompt += f"描述: {robot_info.get('description', '')}\n"
            
            if 'capabilities' in robot_info:
                prompt += "### 能力:\n"
                for cap_name, cap_info in robot_info['capabilities'].items():
                    prompt += f"- **{cap_name}**: {cap_info.get('description', '')}\n"
                    if 'actions' in cap_info:
                        for action in cap_info['actions']:
                            prompt += f"  - {action}\n"
            
            prompt += "\n"
        
        return prompt

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """
        从 LLM 响应中提取 JSON
        
        处理多种格式：
        - 纯 JSON
        - ```json ... ``` 代码块
        - markdown 格式带其他文本
        """
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 ```json``` 代码块
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 尝试查找 { ... } 模式
        brace_match = re.search(r'\{.*\}', text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass
        
        logger.warning(f"无法解析 JSON 响应: {text[:100]}")
        return {}

    def analyze_intent(self, instruction: str, robots: List[Dict]) -> IntentAnalysis:
        """
        分析用户意图
        
        Args:
            instruction: 用户指令
            robots: 可用机器人列表
            
        Returns:
            IntentAnalysis 对象
        """
        try:
            schema_info = self._get_schema_prompt()
            robots_info = json.dumps(robots, ensure_ascii=False, indent=2)
            
            prompt = f"""请分析以下用户指令，判断是信息查询还是任务请求。

{schema_info}

当前可用的机器人：
```json
{robots_info}
```

用户指令：{instruction}

请以 JSON 格式回复，包含以下字段：
{{
  "intent_type": "query 或 task",
  "confidence": 0.0-1.0 之间的置信度,
  "primary_action": "navigate/inspect/transport/manipulate/query/general",
  "description": "意图的人类可读描述",
  "requires_robots": true/false,
  "estimated_duration_ms": 预计执行时长（毫秒），
  "parameters": {{...额外参数，如地点、对象等...}}
}}

重要：只返回 JSON，不要其他内容。"""
            
            logger.info(f"分析意图: {instruction}")
            
            response = self.client.chat.completions.create(
                model=self.intent_model,
                messages=[
                    {"role": "system", "content": "你是一个机器人任务分析助手。分析用户指令的意图类型。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.intent_temperature,
                top_p=self.intent_top_p,
                extra_body={
                    "penalty_score": self.intent_penalty_score,
                    "stop": []
                }
            )
            
            # 安全处理响应
            if not response or not response.choices or len(response.choices) == 0:
                raise ValueError(f"LLM 响应为空: {response}")
            
            response_text = response.choices[0].message.content
            if not response_text:
                raise ValueError("LLM 返回的内容为空")
            
            logger.debug(f"API 响应: {response_text[:200]}")
            
            result = self._parse_json_response(response_text)
            
            return IntentAnalysis(
                intent_type=result.get('intent_type', 'task'),
                confidence=float(result.get('confidence', 0.7)),
                primary_action=result.get('primary_action', 'general'),
                description=result.get('description', instruction),
                requires_robots=result.get('requires_robots', True),
                estimated_duration_ms=int(result.get('estimated_duration_ms', 0)),
                parameters=result.get('parameters', {})
            )
        
        except Exception as e:
            logger.error(f"意图分析失败: {e}")
            return IntentAnalysis(
                intent_type="task",
                confidence=0.5,
                primary_action="general",
                description=instruction,
                requires_robots=True,
                estimated_duration_ms=0,
                parameters={}
            )

    def generate_query_response(self, instruction: str, robots: List[Dict]) -> Dict[str, Any]:
        """
        生成查询响应
        
        Args:
            instruction: 用户查询
            robots: 机器人列表
            
        Returns:
            包含答案的字典
        """
        try:
            robots_info = json.dumps(robots, ensure_ascii=False, indent=2)
            
            prompt = f"""根据以下机器人信息和用户问题，生成一个专业的回答。

可用的机器人：
```json
{robots_info}
```

用户问题：{instruction}

请以自然语言回答这个问题，提供有用的信息。"""
            
            logger.info(f"处理查询: {instruction}")
            
            response = self.client.chat.completions.create(
                model=self.intent_model,
                messages=[
                    {"role": "system", "content": "你是一个机器人系统助手。简洁地回答用户问题。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.intent_temperature,
                top_p=self.intent_top_p,
                extra_body={
                    "penalty_score": self.intent_penalty_score,
                    "stop": []
                }
            )
            
            # 安全处理响应
            if not response or not response.choices or len(response.choices) == 0:
                raise ValueError(f"LLM 响应为空: {response}")
            
            answer = response.choices[0].message.content
            if not answer:
                raise ValueError("LLM 返回的内容为空")
            
            return {
                "type": "information",
                "status": "ANSWERED",
                "question": instruction,
                "answer": answer,
                "sources": ["robot_status", "llm_response"],
                "model": self.intent_model
            }
        
        except Exception as e:
            logger.error(f"查询响应生成失败: {e}")
            return {
                "type": "information",
                "status": "ERROR",
                "question": instruction,
                "answer": f"抱歉，无法处理您的查询: {str(e)}",
                "sources": [],
                "model": self.intent_model
            }

    def generate_task_plan(
        self,
        instruction: str,
        intent: IntentAnalysis,
        robots: List[Dict],
        site: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成任务计划
        
        使用 LLM 进行模板匹配和参数提取，同时返回 JSON 格式参数
        """
        try:
            # 第一步：使用 LLM 进行模板匹配和参数提取
            template_result = self.template_engine.apply_template(instruction, self.schema)
            
            if not template_result:
                logger.warning(f"LLM 模板匹配失败，使用默认规划")
                return self._generate_task_plan_with_llm(
                    instruction, intent, robots, site
                )
            
            matched = template_result.get("matched", False)
            template_name = template_result.get("template_name", "general")
            params = template_result.get("params", {})
            confidence = template_result.get("confidence", 0.0)
            
            logger.info(f"LLM 模板匹配: {template_name} (confidence: {confidence:.2f})")
            
            # 如果模板匹配且置信度较高，直接使用模板生成的计划
            if matched and confidence > 0.5:
                logger.info(f"使用 LLM 匹配的模板 '{template_name}' 生成任务计划")
                payload = {
                    "run_id": f"run_{int(__import__('time').time() * 1000)}",
                    "status": "PLANNING",
                    "task_type": intent.primary_action,
                    "instruction": instruction,
                    "timestamp": __import__('datetime').datetime.now().isoformat() + 'Z',
                    "model": "llm-template-matching",
                    "template_used": template_name,
                    "template_confidence": confidence,
                    "params": params,  # JSON 格式参数
                    "llm_global_planning": template_result.get("llm_global_planning", []),
                    "robot_tool_calls": template_result.get("robot_tool_calls", {}),
                    "constraints": template_result.get("constraints", [])
                }
                payload["execution_supervision"] = self.executor.preview(payload, instruction)
                return payload
            
            # 第二步：如果模板不匹配或置信度低，使用高性能 LLM 直接生成
            logger.info(f"模板匹配置信度不足或未匹配，使用 {self.planning_model} 直接生成任务计划")
            plan = self._generate_task_plan_with_llm(
                instruction, intent, robots, site
            )
            
            # 补充 LLM 提取的参数
            plan["llm_matched_template"] = template_name
            plan["llm_extracted_params"] = params
            
            return plan
        
        except Exception as e:
            logger.error(f"任务规划生成失败: {e}", exc_info=True)
            return {
                "run_id": f"run_{int(__import__('time').time() * 1000)}",
                "status": "ERROR",
                "task_type": intent.primary_action,
                "instruction": instruction,
                "timestamp": __import__('datetime').datetime.now().isoformat() + 'Z',
                "model": "llm-template-matching",
                "error": str(e)
            }
    
    def _generate_task_plan_with_llm(
        self,
        instruction: str,
        intent: IntentAnalysis,
        robots: List[Dict],
        site: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        使用 LLM 直接生成任务计划
        
        并返回结构化的 JSON 参数
        """
        try:
            schema_info = self._get_schema_prompt()
            robots_info = json.dumps(robots, ensure_ascii=False, indent=2)
            
            prompt = f"""请根据用户指令、意图分析和可用的机器人，生成详细的任务执行计划。

{schema_info}

可用的机器人：
```json
{robots_info}
```

用户指令：{instruction}
意图分析：{json.dumps({
                "intent_type": intent.intent_type,
                "primary_action": intent.primary_action,
                "description": intent.description,
                "requires_robots": intent.requires_robots
            }, ensure_ascii=False)}

请以 JSON 格式生成任务计划，包含以下字段：
{{
  "global_planning": [
    {{
      "task_order": 0,
      "robot_id": "机器人ID",
      "task": "任务名称",
      "description": "任务描述",
      "estimated_duration_ms": 预计耗时（毫秒）
    }}
  ],
  "robot_tool_calls": {{
    "robot_id": [
      {{
        "action": "action_name",
        "arguments": {{ "param": "value" }},
        "status": "pending"
      }}
    ]
  }},
  "parameters": {{
    "extracted_params": "从指令中提取的参数（JSON格式）"
  }},
  "constraints": ["约束条件列表"]
}}

重要：
1. 只返回 JSON，不要其他内容
2. parameters 字段中必须包含从指令中提取的结构化参数

意图类型：{intent.primary_action}
主要任务描述：{intent.description}
预计耗时：{intent.estimated_duration_ms}ms

{'地点限制：' + site if site else ''}

请生成详细的任务执行计划，并提取所有相关的结构化参数。"""
            
            logger.info(f"用 {self.planning_model} 生成任务计划: {instruction}")
            
            response = self.client.chat.completions.create(
                model=self.planning_model,
                messages=[
                    {"role": "system", "content": "你是一个专业的机器人任务规划专家。根据用户的自然语言指令和机器人的能力，生成最优的任务执行计划，并提取结构化参数。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.planning_temperature,
                top_p=self.planning_top_p,
                extra_body={
                    "penalty_score": self.planning_penalty_score,
                    "stop": [],
                    "enable_thinking": self.planning_enable_thinking
                }
            )
            
            # 安全处理响应
            if not response or not response.choices or len(response.choices) == 0:
                raise ValueError(f"LLM 响应为空: {response}")
            
            response_text = response.choices[0].message.content
            if not response_text:
                raise ValueError("LLM 返回的内容为空")
            
            logger.debug(f"任务规划响应: {response_text[:500]}")
            
            plan = self._parse_json_response(response_text)
            logger.info(f"解析的规划数据: {json.dumps(plan, ensure_ascii=False)[:200]}")
            
            payload = {
                "run_id": f"run_{int(__import__('time').time() * 1000)}",
                "status": "PLANNING",
                "task_type": intent.primary_action,
                "instruction": instruction,
                "timestamp": __import__('datetime').datetime.now().isoformat() + 'Z',
                "model": self.planning_model,
                "llm_global_planning": plan.get("global_planning", []),
                "robot_tool_calls": plan.get("robot_tool_calls", {}),
                "parameters": plan.get("parameters", {}),
                "constraints": plan.get("constraints", [])
            }
            payload["execution_supervision"] = self.executor.preview(payload, instruction)
            return payload
        
        except Exception as e:
            logger.error(f"LLM 任务规划生成失败: {e}", exc_info=True)
            raise


def create_planner(schema_path: Optional[Path] = None, api_key: Optional[str] = None) -> BaiduPlanner:
    """
    创建百度千帆规划器
    
    Args:
        schema_path: schema 文件路径
        api_key: API 密钥
        
    Returns:
        BaiduPlanner 实例
    """
    return BaiduPlanner(schema_path=schema_path, api_key=api_key)
