# LLM 配置指南

## 概述

系统采用**分阶段模型策略**：
- **意图识别与Template匹配** → 轻量级模型 (qwen3-8b)
- **具体规划** → 高性能模型 (ernie-4.5-21b-a3b-thinking)

## .env 配置

```properties
# 百度千帆 API 配置
PLANNER_TYPE=baidu
BAIDU_API_KEY=your-api-key-here

# ===== 意图识别与Template匹配配置（轻量级模型）=====
MATCHING_MODEL=qwen3-8b
MATCHING_TEMPERATURE=0.7
MATCHING_TOP_P=0.8
MATCHING_PENALTY_SCORE=1
MATCHING_ENABLE_THINKING=false

# ===== 具体规划配置（高性能模型）=====
PLANNING_MODEL=ernie-4.5-21b-a3b-thinking
PLANNING_TEMPERATURE=0.3
PLANNING_TOP_P=0.8
PLANNING_PENALTY_SCORE=0
PLANNING_ENABLE_THINKING=true
```

## 工作流程

### 1. 意图识别阶段
- 使用 `MATCHING_MODEL` (qwen3-8b)
- 快速分类用户指令
- 成本低，速度快

### 2. Template匹配阶段
- 使用 LLM 进行**语义匹配**
- 匹配到预定义模板 → 直接使用模板生成任务
- 未匹配 → 进入第3步

### 3. 具体规划阶段
- 使用 `PLANNING_MODEL` (ernie-4.5-21b-a3b-thinking)
- 高质量推理和思维链
- 为复杂任务生成最优规划

## 模型选择建议

| 场景 | 推荐模型 | 原因 |
|------|---------|------|
| 意图识别、分类 | qwen3-8b | 快速、低成本 |
| Template匹配 | qwen3-8b | 足够的语义理解能力 |
| 复杂规划、推理 | ernie-4.5-21b-a3b | 思维链、高质量 |

## 性能优化

### 成本优化
- 优先使用模板（0 API 调用）
- 次选 qwen3-8b（便宜）
- 最后才用 ernie-4.5-21b（昂贵但高质）

### 速度优化
- qwen3-8b 响应速度快
- 预定义模板几乎零延迟

## 扩展新模板

在 `task_templates.py` 中添加新的 `Template` 类：

```python
class YourTemplate(TaskTemplate):
    def __init__(self):
        super().__init__(
            name="your_template_name",
            pattern=r"正则表达式模式",
            priority=8  # 优先级（数字越小越优先）
        )
    
    def extract_params(self, instruction: str) -> Dict[str, Any]:
        # 从指令中提取参数
        return {"param1": "value1"}
    
    def generate_tool_calls(self, params: Dict[str, Any]) -> Dict[str, List[Dict]]:
        # 生成机器人的 tool calls
        return {
            "robot_id": [
                {"action": "action_name", "arguments": {...}, "status": "pending"}
            ]
        }
    
    def generate_global_planning(self, params: Dict[str, Any]) -> List[Dict]:
        # 生成全局规划
        return [{
            "task_order": 0,
            "robot_id": "robot_id",
            "task": "task_name",
            "description": "description"
        }]
```

然后在 `TemplateEngine.__init__()` 中注册：

```python
self.templates: List[TaskTemplate] = [
    NotificationTemplate(),
    InspectionTemplate(),
    TransportTemplate(),
    YourTemplate(),  # 添加你的模板
]
```

## 调试技巧

### 查看 LLM 匹配过程
```python
# 在 task_templates.py 中调整日志级别
logger.setLevel(logging.DEBUG)
```

### 测试单个模板
```python
from task_templates import NotificationTemplate

template = NotificationTemplate()
params = template.extract_params("通知张三和李四来2205开会")
print(params)
```

## 常见问题

### Q: 为什么有时候模板不匹配？
A: LLM 匹配失败时，系统会自动使用高性能模型进行规划，确保任务始终能被正确处理。
可以通过以下方式改进匹配准确度：
1. 增加更多变体的模板
2. 优化 LLM Prompt
3. 检查 MATCHING_MODEL 是否可用

### Q: 如何禁用思维链以降低成本？
A: 修改 `.env` 文件：
```properties
PLANNING_ENABLE_THINKING=false
```

### Q: 可以在运行时动态切换模型吗？
A: 可以。修改 `.env` 文件后，重启应用即可。或者直接在代码中修改环境变量（需要在初始化前）。
