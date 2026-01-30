"""Scenario-specific task template implementations and registry metadata."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from task_templates_core import TaskTemplate


class NotificationTemplate(TaskTemplate):
    """通知模板: 通知某人到某地做某事"""

    def __init__(self):
        super().__init__(name="notification", priority=5)

    @staticmethod
    def _route_planning(recipients: List[str], fallback: str) -> List[str]:
        """Return the navigation sweep route (stubbed for now)."""
        if fallback:
            return [fallback]
        return recipients or []

    def extract_params(self, instruction: str) -> Dict[str, Any]:
        raise NotImplementedError("NotificationTemplate 参数由 LLM 提取，此方法已弃用")

    def generate_tool_calls(self, params: Dict[str, Any]) -> Dict[str, List[Dict]]:
        recipients = params.get("recipients", [])
        location = params.get("location", "")
        reason = params.get("reason", "开会")
        robot_id = "QR-SZZX-0001"

        tool_calls: List[Dict[str, Any]] = []

        # Consolidated search that can finish early when everyone is located.
        if recipients:
            route = self._route_planning(recipients, location)
            tool_calls.append({
                "action": "search_people",
                "arguments": {
                    "targets": recipients,
                    "stop_when_all_found": True,
                    "sweep_strategy": {
                        "preferred_route": route,
                        "max_loops": 1
                    }
                },
                "metadata": {
                    "adaptive": True,
                    "reason": "移动过程中同步感知，找到所有目标后提前终止剩余路线"
                },
                "status": "pending"
            })

        if location:
            tool_calls.append({
                "action": "return_to_location",
                "arguments": {
                    "location": location,
                    "reason": "通知结束后返回会议室等候"
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


__all__ = [
    "NotificationTemplate",
    "InspectionTemplate",
    "TransportTemplate",
    "TEMPLATE_REGISTRY_DATA",
    "TEMPLATE_HANDLER_FACTORIES",
]
