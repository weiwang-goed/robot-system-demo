from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from task_templates_core import TemplateEngine


@dataclass
class CommandStep:
    """Normalized representation of a robot tool call ready for supervision."""

    step_id: str
    robot_id: str
    action: str
    arguments: Dict[str, Any]
    timeout_sec: int = 45
    retriable: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "robot_id": self.robot_id,
            "action": self.action,
            "arguments": self.arguments,
            "timeout_sec": self.timeout_sec,
            "retriable": self.retriable,
            "metadata": self.metadata,
            "status": "pending",
        }


@dataclass
class ExecutionEvent:
    """Point-in-time record emitted while executing a command."""

    step_id: str
    robot_id: str
    action: str
    status: str
    reason: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    )

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "step_id": self.step_id,
            "robot_id": self.robot_id,
            "action": self.action,
            "status": self.status,
            "timestamp": self.timestamp,
        }
        if self.reason:
            data["reason"] = self.reason
        return data


@dataclass
class ReplanContext:
    """Reasoned request for replanning after a failure/timeout."""

    step_id: str
    reason: str
    status: str
    attempts: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "reason": self.reason,
            "status": self.status,
            "attempts": self.attempts,
            "metadata": self.metadata,
        }


class SupervisedExecutor:
    """Plans how commands are supervised, terminated, and potentially replanned."""

    def __init__(self, template_engine: Optional["TemplateEngine"] = None):
        self.template_engine = template_engine

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def preview(self, plan: Dict[str, Any], instruction: str = "") -> Dict[str, Any]:
        """Return supervision metadata without mutating execution state."""

        steps = self._build_steps(plan, attach_step_ids=True)
        adaptive = [a for a in (self._build_adaptive_descriptor(step) for step in steps) if a]
        summary = {
            "steps": [step.to_dict() for step in steps],
            "supervision_rules": self._default_rules(),
            "adaptive_search": adaptive,
            "events": [],
            "replan_decisions": [],
            "next_actions": self._predict_next_actions(steps),
            "instruction": instruction,
        }
        return summary

    def execute_with_feedback(
        self,
        plan: Dict[str, Any],
        instruction: str,
        runtime_feedback: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Simulate supervised execution using optional runtime feedback per step."""

        runtime_feedback = runtime_feedback or {}
        summary = self.preview(plan, instruction)
        events: List[ExecutionEvent] = []
        replan: List[ReplanContext] = []

        for step in summary["steps"]:
            feedback = runtime_feedback.get(step["step_id"], {})
            status = feedback.get("status", "success")
            reason = feedback.get("reason")
            events.append(
                ExecutionEvent(
                    step_id=step["step_id"],
                    robot_id=step["robot_id"],
                    action=step["action"],
                    status=status,
                    reason=reason,
                )
            )

            if status in {"timeout", "failed", "terminated"}:
                replan.append(
                    ReplanContext(
                        step_id=step["step_id"],
                        status=status,
                        reason=reason or "unknown",
                        metadata={"robot_id": step["robot_id"], "action": step["action"]},
                    )
                )
                break

        summary["events"] = [event.to_dict() for event in events]
        summary["replan_decisions"] = [ctx.to_dict() for ctx in replan]
        return summary

    def request_replan(
        self,
        instruction: str,
        failure_context: ReplanContext,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Invoke the template engine again with the previous failure reason."""

        if not self.template_engine:
            return None

        hint = f"上一次失败原因: {failure_context.reason} (step={failure_context.step_id})"
        metadata = {"failure_reason": failure_context.reason}
        if failure_context.metadata:
            metadata.update(failure_context.metadata)

        # Provide the hint via a simple JSON schema so LLM can consider it.
        schema_with_hint = dict(schema or {})
        schema_with_hint["supervision_hint"] = hint
        result = self.template_engine.apply_template(instruction, schema_with_hint)
        if result is not None:
            result.setdefault("constraints", []).append(hint)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_steps(self, plan: Dict[str, Any], attach_step_ids: bool = False) -> List[CommandStep]:
        robot_calls = plan.get("robot_tool_calls") or {}
        steps: List[CommandStep] = []
        for robot_id, calls in robot_calls.items():
            if not isinstance(calls, list):
                continue
            for idx, call in enumerate(calls):
                action = call.get("action", "unknown")
                step_id = call.get("step_id") or self._make_step_id(robot_id, idx, action)
                if attach_step_ids:
                    call["step_id"] = step_id
                metadata = call.get("metadata") or {}
                metadata.setdefault("call_index", idx)
                step = CommandStep(
                    step_id=step_id,
                    robot_id=robot_id,
                    action=action,
                    arguments=call.get("arguments", {}),
                    timeout_sec=metadata.get("timeout_sec", 45),
                    retriable=metadata.get("retriable", True),
                    metadata=metadata,
                )
                steps.append(step)
        return steps

    def _default_rules(self) -> Dict[str, Any]:
        return {
            "timeout_behavior": "cancel-current-and-request-replan",
            "abort_signal": "operator_stop",
            "max_retries": 1,
            "description": "顺序执行命令，若失败/超时/终止则立即停止并触发重新规划",
        }

    def _predict_next_actions(self, steps: List[CommandStep]) -> List[Dict[str, Any]]:
        preview_count = min(3, len(steps))
        return [steps[i].to_dict() for i in range(preview_count)]

    def _build_adaptive_descriptor(self, step: CommandStep) -> Optional[Dict[str, Any]]:
        if step.action != "search_people":
            return None
        targets = step.arguments.get("targets") or []
        return {
            "step_id": step.step_id,
            "robot_id": step.robot_id,
            "targets": targets,
            "found_targets": [],
            "stop_when_all_found": step.arguments.get("stop_when_all_found", True),
            "waypoints": step.arguments.get("sweep_strategy", {}).get("preferred_route", []),
            "note": step.metadata.get(
                "reason",
                "移动与感知同步，找到所有目标后跳过剩余路线",
            ),
        }

    def _make_step_id(self, robot_id: str, index: int, action: str) -> str:
        safe_action = action.replace(" ", "_")
        return f"{robot_id}-{index:02d}-{safe_action}"
