# LLM 驱动的模板匹配改造 - 修改总结

日期: 2026-01-27

## 概述

按照用户要求，对整个机器人任务规划系统进行了以下核心修改：

1. **只使用 LLM 匹配 template** - 去掉了原来的规则匹配
2. **使用 qwen3-8b 模型** - 轻量级但高效的模板匹配
3. **同时返回 JSON 格式参数** - 提取结构化的任务参数

---

## 详细修改

### 1. `task_templates.py` - 核心改造

#### 变更内容：

- **移除了纯规则匹配**：原来的 `matches()` 方法和正则表达式匹配被 LLM 调用替代
- **新增 LLM 匹配能力**：`TemplateEngine.apply_template()` 现在使用 OpenAI API 调用百度千帆的 qwen3-8b 模型
- **结构化参数提取**：LLM 直接提取 JSON 格式参数，包括：
  - notification: `recipients`, `location`, `reason`
  - inspection: `area`, `take_photo`, `inspection_type`
  - transport: `item`, `source`, `destination`
  
#### 新增方法：

```python
def apply_template(self, instruction: str, schema: Dict[str, Any] = None):
    """使用 LLM 匹配模板并提取参数"""
    # 返回格式：
    {
        "template_name": "通知/巡检/运输/general",
        "matched": True/False,
        "confidence": 0.0-1.0,
        "params": {...},  # JSON 格式参数
        "llm_global_planning": [...],
        "robot_tool_calls": {...},
        "constraints": [...]
    }
```

#### 关键特性：

- LLM 自动选择最适合的模板
- 提供匹配置信度（0.0-1.0）
- 置信度低于 0.5 时会转向直接 LLM 规划
- 智能参数提取，避免手工正则表达式维护

---

### 2. `llm_planner_baidu.py` - 集成改造

#### 变更内容：

- **修改 `generate_task_plan()` 方法**：
  - 第一步：使用 LLM 进行模板匹配和参数提取
  - 如果置信度 > 0.5：使用模板生成的任务序列
  - 如果置信度 ≤ 0.5：转向高性能 LLM 直接规划
  
- **增强 `_generate_task_plan_with_llm()` 方法**：
  - 返回 JSON 格式参数（`parameters` 字段）
  - LLM 提示词明确要求提取结构化参数
  - 规划结果包含：`global_planning`, `robot_tool_calls`, `parameters`, `constraints`

#### 响应格式示例：

```json
{
  "run_id": "run_1706335200000",
  "status": "PLANNING",
  "task_type": "navigate",
  "instruction": "通知李涛和吴晋来2215开会",
  "timestamp": "2026-01-27T...",
  "model": "llm-template-matching",
  "template_used": "notification",
  "template_confidence": 0.95,
  "params": {
    "recipients": ["李涛", "吴晋"],
    "location": "2215",
    "reason": "开会"
  },
  "llm_global_planning": [...],
  "robot_tool_calls": {...},
  "constraints": [...]
}
```

---

### 3. `.env` 配置

#### 已验证的配置：

```
PLANNER_TYPE=baidu
BAIDU_API_KEY=bce-v3/ALTAK-FIyM1bJHsGEYqMv6Ub6rI/...

# ===== 意图识别配置（轻量级模型 Qwen-8b）=====
INTENT_MODEL=qwen3-8b          # 用于意图识别和模板匹配
INTENT_TEMPERATURE=0.3         # 低温度保证准确性
INTENT_TOP_P=0.8
INTENT_PENALTY_SCORE=1

# ===== 复杂任务规划配置（高性能模型）=====
PLANNING_MODEL=ernie-4.5-21b-a3b-thinking
PLANNING_TEMPERATURE=0.3
PLANNING_TOP_P=0.8
PLANNING_PENALTY_SCORE=1
PLANNING_ENABLE_THINKING=true
```

---

## API 变化

### 之前的 API 响应：

```json
{
  "model": "template",
  "template_used": "notification",
  "params": {...}
}
```

### 现在的 API 响应：

```json
{
  "model": "llm-template-matching",
  "template_used": "notification",
  "template_confidence": 0.95,
  "params": {...},              // 模板提取的参数
  "llm_global_planning": [...],
  "robot_tool_calls": {...},
  "parameters": {...},          // LLM 提取的额外参数
  "constraints": [...]
}
```

---

## 优势

1. **灵活性更强** - LLM 可以处理更复杂和多样化的表述方式
2. **参数提取更准确** - 无需维护复杂的正则表达式
3. **置信度指标** - 可以评估匹配的可靠性
4. **自动参数识别** - 自动从输入中提取结构化参数
5. **降低维护成本** - 无需为每个新模式添加新的正则表达式

---

## 使用流程

```
用户指令
    ↓
分析意图 (qwen3-8b)
    ↓
LLM 模板匹配 + 参数提取 (qwen3-8b)
    ↓
    ├─ 置信度 > 0.5 → 使用模板生成的任务序列
    │
    └─ 置信度 ≤ 0.5 → 使用高性能 LLM 直接规划 (ernie-4.5)
            ↓
        返回结构化的 JSON 参数
            ↓
        执行任务计划
```

---

## 测试

运行测试脚本验证改造：

```bash
cd backend
python test_llm_matching.py
```

测试内容：
- ✓ LLM 模板匹配准确性
- ✓ 参数提取完整性
- ✓ 完整的任务规划流程
- ✓ JSON 格式参数返回

---

## 依赖项

无新增依赖，使用现有的：
- `openai` (用于 API 调用)
- `python-dotenv` (用于环境变量加载)

---

## 下一步

1. 在前端集成新的 `parameters` 字段显示
2. 根据需要调整置信度阈值（当前为 0.5）
3. 根据实际反馈优化 qwen3-8b 的提示词
4. 考虑添加更多的模板类型或参数字段

---

## 文件修改清单

- ✅ `backend/task_templates.py` - 完全改造为 LLM 驱动
- ✅ `backend/llm_planner_baidu.py` - 集成 LLM 模板匹配，增强参数提取
- ✅ `backend/.env` - 验证配置（无需修改）
- ✅ `backend/test_llm_matching.py` - 新增测试脚本

---

## 验证清单

- ✅ 无语法错误
- ✅ 模块能正确导入
- ✅ API 兼容性保持（返回格式扩展，不破坏原有字段）
- ✅ 支持 JSON 格式参数
