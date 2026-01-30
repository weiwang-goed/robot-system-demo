"""Convenience exports for the task template system."""

from typing import List, Optional

from task_templates_core import (
    TaskTemplate,
    TemplateEngine,
    TemplateSpec,
    build_default_template_specs,
)
from task_templates_builtin import (
    NotificationTemplate,
    InspectionTemplate,
    TransportTemplate,
    TEMPLATE_HANDLER_FACTORIES,
    TEMPLATE_REGISTRY_DATA,
)


DEFAULT_TEMPLATES: List[TemplateSpec] = build_default_template_specs()
_template_engine: Optional[TemplateEngine] = None


def get_template_engine() -> TemplateEngine:
    """Return a shared TemplateEngine instance configured with built-in templates."""
    global _template_engine
    if _template_engine is None:
        _template_engine = TemplateEngine(templates=build_default_template_specs())
    return _template_engine


__all__ = [
    "TaskTemplate",
    "TemplateSpec",
    "TemplateEngine",
    "NotificationTemplate",
    "InspectionTemplate",
    "TransportTemplate",
    "TEMPLATE_REGISTRY_DATA",
    "TEMPLATE_HANDLER_FACTORIES",
    "build_default_template_specs",
    "get_template_engine",
    "DEFAULT_TEMPLATES",
]
