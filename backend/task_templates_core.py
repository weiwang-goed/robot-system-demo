"""
task_templates_core.py
=====================
任务模板系统 - 核心框架

包含：
- TaskTemplate 基类
- TemplateEngine 引擎
- 模板注册 JSON 元数据与具体实现
"""

import json
import os
import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger(__name__)
load_dotenv()


@dataclass
class TaskTemplate(ABC):
    """任务模板基类"""
    name: str
    priority: int = 10

    @abstractmethod
    def extract_params(self, instruction: str) -> Dict[str, Any]:
        """从自然语言指令中提取参数"""
        raise NotImplementedError

    @abstractmethod
    def generate_tool_calls(self, params: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """根据参数生成机器人动作序列"""
        raise NotImplementedError

    @abstractmethod
    def generate_global_planning(self, params: Dict[str, Any]) -> List[Dict]:
        """生成全局规划描述"""
        raise NotImplementedError


@dataclass
class ParameterSpec:
    """模板参数的元数据，驱动 LLM 参数提取"""
    name: str
    description: str
    param_type: str = "string"
    required: bool = True
    example: Optional[Any] = None

    def to_prompt_dict(self) -> Dict[str, Any]:
        data = {
            "name": self.name,
            "description": self.description,
            "type": self.param_type,
            "required": self.required
        }
        if self.example is not None:
            data["example"] = self.example
        return data


@dataclass
class TemplateSpec:
    """模板注册信息（包含元数据与处理器）"""
    name: str
    description: str
    parameters: List[ParameterSpec] = field(default_factory=list)
    handler: TaskTemplate = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def priority(self) -> int:
        return self.handler.priority if self.handler else 10

    def to_prompt_dict(self) -> Dict[str, Any]:
        data = {
            "name": self.name,
            "description": self.description,
            "parameters": [p.to_prompt_dict() for p in self.parameters]
        }
        if self.metadata:
            data["metadata"] = self.metadata
        return data


class TemplateEngine:
    """任务模板引擎 - 使用 LLM 完成模板选择与参数提取"""

    def __init__(self, templates: Optional[List[TemplateSpec]] = None):
        self.template_specs: List[TemplateSpec] = templates or []
        self.template_specs.sort(key=lambda spec: spec.priority)
        self.template_map: Dict[str, TemplateSpec] = {spec.name: spec for spec in self.template_specs}
        self.templates: List[TaskTemplate] = [spec.handler for spec in self.template_specs if spec.handler]

        try:
            api_key = os.getenv("BAIDU_API_KEY")
            if not api_key:
                raise ValueError("BAIDU_API_KEY 环境变量未设置")

            self.client = OpenAI(base_url='https://qianfan.baidubce.com/v2', api_key=api_key)
            self.matching_model = os.getenv("INTENT_MODEL", "qwen3-8b")
            self.matching_temperature = float(os.getenv("INTENT_TEMPERATURE", "0.3"))
            self.matching_top_p = float(os.getenv("INTENT_TOP_P", "0.8"))
            logger.info(
                "初始化 LLM 模板引擎，使用模型 %s，已注册模板: %s",
                self.matching_model,
                ", ".join(self.template_map.keys()) or "无"
            )
        except Exception as exc:
            logger.warning("LLM 初始化失败: %s", exc)
            self.client = None

    def register_template(self, template_spec: TemplateSpec) -> None:
        """注册新的模板规格"""
        self.template_specs.append(template_spec)
        self.template_specs.sort(key=lambda spec: spec.priority)
        self.template_map = {spec.name: spec for spec in self.template_specs}
        self.templates = [spec.handler for spec in self.template_specs if spec.handler]
        logger.info("注册模板: %s (优先级: %s)", template_spec.name, template_spec.priority)

    def apply_template(self, instruction: str, schema: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """使用 LLM 匹配模板并产出参数"""
        if not self.client:
            logger.warning("LLM 客户端未初始化，无法进行模板匹配")
            return None

        if not self.template_specs:
            logger.warning("当前未注册任何模板，无法匹配")
            return None

        try:
            template_catalog_json = self._get_template_catalog_json()
            prompt = (
                "请分析以下用户指令，并根据任务模板注册表(JSON)选择最合适的模板。"
                "输出的所有字段必须严格遵守注册表中的参数定义（类型与必填要求）。\n\n"
                f"任务模板注册表：\n{template_catalog_json}\n\n"
                f"用户指令：{instruction}\n\n"
                "请仅输出 JSON，格式如下：\n"
                "{\n"
                "  \"template_name\": \"匹配的模板名称（不匹配则返回 general）\",\n"
                "  \"matched\": true/false,\n"
                "  \"confidence\": 介于 0 和 1 的数字,\n"
                "  \"description\": \"简短原因说明\",\n"
                "  \"parameters\": { ...严格依据模板注册表... }\n"
                "}\n"
                "注意 recipients 始终是数组，transport.source 可为 null 表示未知起点。"
            )

            logger.info("使用 LLM 匹配模板: %s", instruction[:50])
            response = self.client.chat.completions.create(
                model=self.matching_model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是任务模板匹配助手，会根据模板注册表输出结构化 JSON。"
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=self.matching_temperature,
                top_p=self.matching_top_p,
                extra_body={
                    "penalty_score": float(os.getenv("INTENT_PENALTY_SCORE", "1")),
                    "stop": []
                }
            )

            response_text = response.choices[0].message.content if response.choices else ""
            logger.debug("LLM 响应: %s", response_text[:200])
            result = self._parse_json_response(response_text)

            if not result or "template_name" not in result:
                logger.warning("LLM 返回格式异常: %s", response_text[:100])
                return None

            template_name = result.get("template_name", "general")
            matched = result.get("matched", False)
            confidence = result.get("confidence", 0.0)
            params = result.get("parameters", {})
            logger.info("模板匹配结果: %s (confidence=%.2f)", template_name, confidence)

            if matched and template_name != "general":
                template_spec = self._find_template_spec(template_name)
                if template_spec and template_spec.handler:
                    return {
                        "template_name": template_name,
                        "matched": True,
                        "confidence": confidence,
                        "params": params,
                        "llm_global_planning": template_spec.handler.generate_global_planning(params),
                        "robot_tool_calls": template_spec.handler.generate_tool_calls(params),
                        "constraints": [
                            f"匹配模板 {template_name}",
                            "参数由 LLM 按注册表提取"
                        ]
                    }

            return {
                "template_name": template_name,
                "matched": matched,
                "confidence": confidence,
                "params": params,
                "llm_global_planning": [],
                "robot_tool_calls": {},
                "constraints": ["未命中特定模板，走通用规划"]
            }

        except Exception as exc:
            logger.error("LLM 模板匹配失败: %s", exc, exc_info=True)
            return None

    def _get_template_catalog_json(self) -> str:
        catalog = [spec.to_prompt_dict() for spec in self.template_specs]
        return json.dumps(catalog, ensure_ascii=False, indent=2)

    def _find_template_spec(self, name: str) -> Optional[TemplateSpec]:
        return self.template_map.get(name)

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        brace_match = re.search(r'\{.*\}', text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning("无法解析 JSON 响应: %s", text[:100])
        return {}


class NotificationTemplate(TaskTemplate):
    """通知模板: 通知某人到某地做某事"""

    def __init__(self):
        super().__init__(name="notification", priority=5)

    def extract_params(self, instruction: str) -> Dict[str, Any]:
        raise NotImplementedError("NotificationTemplate 参数由 LLM 提取，此方法已弃用")

    def generate_tool_calls(self, params: Dict[str, Any]) -> Dict[str, List[Dict]]:
        recipients = params.get("recipients", [])
        location = params.get("location", "")
        reason = params.get("reason", "开会")
        robot_id = "QR-SZZX-0001"

        tool_calls = []
        for recipient in recipients:
            tool_calls.append({
                "action": "search_person",
                "arguments": {
                    "person_name": recipient,
                    "search_scope": "building"
                },
                "status": "pending"
            })

        tool_calls.append({
            "action": "navigation",
            "arguments": {
                "location": location,
                "priority": "high"
            },
            "status": "pending"
        })

        tool_calls.append({
            "action": "speech_synthesis",
            "arguments": {
                "recipients": recipients,
                "location": location,
                "message": f"请{','.join(recipients)}到{location}{reason}"
            },
            "status": "pending"
        })

        return {robot_id: tool_calls}

    def generate_global_planning(self, params: Dict[str, Any]) -> List[Dict]:
        recipients = params.get("recipients", [])
        location = params.get("location", "")
        reason = params.get("reason", "开会")
        return [
            {
                "task_order": 0,
                "robot_id": "QR-SZZX-0001",
                "task": "通知任务",
                "description": f"通知 {', '.join(recipients)} 到 {location} {reason}"
            }
        ]


class InspectionTemplate(TaskTemplate):
    """巡检模板: 巡视某区域并可能拍照"""

    def __init__(self):
        super().__init__(name="inspection", priority=6)

    def extract_params(self, instruction: str) -> Dict[str, Any]:
        raise NotImplementedError("InspectionTemplate 参数由 LLM 提取，此方法已弃用")

    def generate_tool_calls(self, params: Dict[str, Any]) -> Dict[str, List[Dict]]:
        area = params.get("area", "")
        take_photo = params.get("take_photo", False)
        robot_id = "QR-XJJG-0001"

        tool_calls = [
            {
                "action": "navigation",
                "arguments": {"location": area},
                "status": "pending"
            },
            {
                "action": "inspection",
                "arguments": {
                    "area": area,
                    "inspection_type": "visual"
                },
                "status": "pending"
            }
        ]

        if take_photo:
            tool_calls.append({
                "action": "capture_image",
                "arguments": {
                    "location": area,
                    "count": 3
                },
                "status": "pending"
            })

        return {robot_id: tool_calls}

    def generate_global_planning(self, params: Dict[str, Any]) -> List[Dict]:
        area = params.get("area", "")
        return [
            {
                "task_order": 0,
                "robot_id": "QR-XJJG-0001",
                "task": "区域巡检",
                "description": f"巡视 {area} 并获取状态信息"
            }
        ]


class TransportTemplate(TaskTemplate):
    """运输/搬运模板: 将物品从一地运送到另一地"""

    def __init__(self):
        super().__init__(name="transport", priority=7)

    def extract_params(self, instruction: str) -> Dict[str, Any]:
        raise NotImplementedError("TransportTemplate 参数由 LLM 提取，此方法已弃用")

    def generate_tool_calls(self, params: Dict[str, Any]) -> Dict[str, List[Dict]]:
        item = params.get("item", "")
        source = params.get("source")
        destination = params.get("destination", "")
        robot_id = "QR-YSXR-0001"

        tool_calls = []
        if source:
            tool_calls.append({
                "action": "navigation",
                "arguments": {"location": source},
                "status": "pending"
            })

        tool_calls.append({
            "action": "pick_up",
            "arguments": {
                "item": item,
                "location": source
            },
            "status": "pending"
        })

        tool_calls.append({
            "action": "navigation",
            "arguments": {"location": destination},
            "status": "pending"
        })

        tool_calls.append({
            "action": "put_down",
            "arguments": {
                "item": item,
                "location": destination
            },
            "status": "pending"
        })

        return {robot_id: tool_calls}

    def generate_global_planning(self, params: Dict[str, Any]) -> List[Dict]:
        item = params.get("item", "")
        source = params.get("source")
        destination = params.get("destination", "")
        description = f"将 {item} 从 {source} 运送到 {destination}" if source else f"将 {item} 运送到 {destination}"
        return [
            {
                "task_order": 0,
                "robot_id": "QR-YSXR-0001",
                "task": "物料运输",
                "description": description
            }
        ]


TEMPLATE_REGISTRY_DATA: List[Dict[str, Any]] = [
    {
        "name": "notification",
        "description": "通知任务（通知某些人到指定地点进行会议或讨论）",
        "parameters": [
            {
                "name": "recipients",
                "type": "list",
                "description": "通知对象的姓名数组，例如 [\"李涛\", \"吴晋\"]，需要提取所有出现的人名",
                "required": True,
                "example": ["李涛", "吴晋"]
            },
            {
                "name": "location",
                "type": "string",
                "description": "需要前往的地点，例如 2215 会议室",
                "required": True,
                "example": "2215"
            },
            {
                "name": "reason",
                "type": "string",
                "description": "通知原因或会议主题",
                "required": False,
                "example": "开会"
            }
        ]
    },
    {
        "name": "inspection",
        "description": "巡检任务（巡视某区域，必要时拍照）",
        "parameters": [
            {
                "name": "area",
                "type": "string",
                "description": "需要巡检的区域名称",
                "required": True,
                "example": "一楼"
            },
            {
                "name": "take_photo",
                "type": "boolean",
                "description": "是否需要拍照记录，true/false",
                "required": False,
                "example": True
            },
            {
                "name": "inspection_type",
                "type": "string",
                "description": "巡检类型，例如 visual/thermal",
                "required": False,
                "example": "visual"
            }
        ]
    },
    {
        "name": "transport",
        "description": "运输任务（将物品从起点搬运到目的地）",
        "parameters": [
            {
                "name": "item",
                "type": "string",
                "description": "需要搬运的物品名称",
                "required": True,
                "example": "物料"
            },
            {
                "name": "source",
                "type": "string",
                "description": "物品所在的起始位置，未知则为 null",
                "required": False,
                "example": "办公室"
            },
            {
                "name": "destination",
                "type": "string",
                "description": "物品要送达的目的地",
                "required": True,
                "example": "仓库"
            }
        ]
    }
]


TEMPLATE_HANDLER_FACTORIES = {
    "notification": NotificationTemplate,
    "inspection": InspectionTemplate,
    "transport": TransportTemplate
}


def build_default_template_specs() -> List[TemplateSpec]:
    """从 JSON 样式的注册表构建 TemplateSpec 列表"""
    specs: List[TemplateSpec] = []
    for entry in TEMPLATE_REGISTRY_DATA:
        parameter_specs = [
            ParameterSpec(
                name=param["name"],
                description=param.get("description", ""),
                param_type=param.get("type", "string"),
                required=param.get("required", True),
                example=param.get("example")
            )
            for param in entry.get("parameters", [])
        ]

        handler_cls = TEMPLATE_HANDLER_FACTORIES.get(entry["name"])
        handler = handler_cls() if handler_cls else None

        extra_metadata = {
            k: v for k, v in entry.items() if k not in {"name", "description", "parameters"}
        }

        specs.append(
            TemplateSpec(
                name=entry["name"],
                description=entry.get("description", ""),
                parameters=parameter_specs,
                handler=handler,
                metadata=extra_metadata
            )
        )

    return specs


def get_template_engine(template_specs: Optional[List[TemplateSpec]] = None) -> TemplateEngine:
    """工厂方法，提供默认模板引擎"""
    specs = template_specs if template_specs is not None else build_default_template_specs()
    return TemplateEngine(templates=specs)


__all__ = [
    "TaskTemplate",
    "ParameterSpec",
    "TemplateSpec",
    "TemplateEngine",
    "NotificationTemplate",
    "InspectionTemplate",
    "TransportTemplate",
    "TEMPLATE_REGISTRY_DATA",
    "build_default_template_specs",
    "get_template_engine"
]
