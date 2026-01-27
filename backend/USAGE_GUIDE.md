# 机器人 LLM Planning 系统使用指南

## 🎯 快速开始

### 1. 文件结构

新增文件：
```
robot_console_dashboard_modular/
├── data/
│   └── robot_behaviors_schema.json      # ✨ 新文件：机器人行为定义
├── backend/
│   ├── app.py                           # ✏️ 修改：集成 LLM Planner
│   ├── llm_planner.py                   # ✨ 新文件：大模型规划引擎
│   └── test_llm_planner.py              # ✨ 新文件：测试脚本
└── LLM_PLANNER_README.md                # ✨ 新文件：详细文档
```

### 2. 快速验证

运行测试脚本：
```bash
cd backend
python test_llm_planner.py
```

预期输出：6 个测试用例，包括查询和任务规划

### 3. API 调用示例

#### 查询示例
```bash
curl -X POST "http://localhost:9000/api/generate_plan" \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "系统里有多少台机器人？"
  }'
```

响应：
```json
{
  "type": "information",
  "status": "ANSWERED",
  "question": "系统里有多少台机器人？",
  "answer": "系统中共有 5 台机器人：...",
  "sources": ["robot_status", "robot_schema"]
}
```

#### 任务规划示例
```bash
curl -X POST "http://localhost:9000/api/generate_plan" \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "将货物从仓库搬运到办公室"
  }'
```

响应：
```json
{
  "run_id": "run_1769054313",
  "status": "PLANNING",
  "task_type": "transport",
  "llm_thinking": "用户要求从pickup_area运输物体到office",
  "llm_global_planning": [
    {
      "task_order": 0,
      "robot_id": "WR-GYL-0001",
      "task": "transport"
    }
  ],
  "robot_tool_calls": {
    "WR-GYL-0001": [
      {"action": "move_to", "arguments": "pickup_area"},
      {"action": "grasp", "arguments": "target_object"},
      {"action": "move_to", "arguments": "office"},
      {"action": "release", "arguments": "office"}
    ]
  }
}
```

## 🔧 工作原理

### 流程图

```
用户指令
   ↓
LLMPlanner.analyze_intent()
   ├─ 查询检测 (information keywords)
   ├─ 任务检测 (action keywords)
   └─ 动作识别 (primary action)
   ↓
   ├→ intent_type == "query"
   │    ↓
   │    generate_query_response()
   │    ↓
   │    返回信息
   │
   └→ intent_type == "task"
        ↓
        generate_task_plan()
        ↓
        选择合适机器人
        ↓
        生成任务序列
        ↓
        生成工具调用
        ↓
        返回任务计划
```

## 📚 支持的指令类型

### 查询类（Information）

| 关键词 | 示例 | 响应类型 |
|--------|------|---------|
| 多少/how many | "有多少台机器人?" | 机器人计数 |
| 在线/online | "哪些机器人在线?" | 在线状态列表 |
| 电量/battery | "电池怎么样?" | 电池状态列表 |
| 是什么/what is | "仓储机器人是什么?" | 机器人描述 |

### 任务类（Task）

| 动作 | 关键词 | 机器人选择 | 示例 |
|------|--------|----------|------|
| 导航 | 移动/前往/去 | 轮式>通用 | "去充电器" |
| 巡检 | 巡检/检查/扫描 | 四足>无人机>轮式 | "对仓库巡检" |
| 运输 | 搬运/运输/送 | 轮式>通用 | "把货物送到B区" |
| 操纵 | 抓取/堆垛/放置 | 轮式>通用 | "堆垛这些箱子" |

## 🤖 机器人能力查询

### 查看特定机器人的能力

```python
from llm_planner import create_planner

planner = create_planner()
schema = planner.schema

# 查看轮式机器人的能力
wheel_robot = schema["robot_behaviors"]["wheel_robot"]
print(wheel_robot["capabilities"])
```

### 支持的机器人类型

1. **轮式机器人** (wheel_robot)
   - 机器人: WR-GYL-0001, WR-SZZX-0001
   - 能力: 导航、抓取、堆垛、拍照、扫描、语音播报

2. **四足机器人** (quadruped_robot)
   - 机器人: QR-SZZX-0001
   - 能力: 导航(复杂地形)、爬升、视觉巡检、热成像、语音对讲

3. **无人机** (drone)
   - 机器人: DR-WX-0001
   - 能力: 起飞、飞行、着陆、航线任务、视频录制

4. **人形机器人** (humanoid_robot)
   - 机器人: 10041B700128
   - 能力: 行走、拾取放置、手势识别

## 🎨 自定义扩展

### 添加新的机器人行为

编辑 `data/robot_behaviors_schema.json`：

```json
{
  "robot_behaviors": {
    "your_robot_type": {
      "category": "你的机器人类型",
      "capabilities": {
        "new_action": {
          "description": "动作描述",
          "parameters": {
            "param1": {
              "type": "string",
              "description": "参数说明"
            }
          },
          "expected_duration_ms": 5000,
          "failure_modes": ["failure1", "failure2"]
        }
      }
    }
  }
}
```

### 添加新的关键词

在 schema 的 `intent_keywords` 部分：

```json
{
  "intent_keywords": {
    "your_intent": ["关键词1", "关键词2", "关键词3"]
  }
}
```

### 自定义意图分析

在 `llm_planner.py` 中修改或继承 `LLMPlanner`：

```python
from llm_planner import LLMPlanner

class CustomPlanner(LLMPlanner):
    def analyze_intent(self, instruction: str):
        # 你的自定义逻辑
        # 例如调用真实的 LLM API
        intent = super().analyze_intent(instruction)
        return intent
```

## 🚀 生产部署建议

### 1. 接入真实 LLM

当前使用关键字匹配，建议升级到真实 LLM：

```python
import openai

def analyze_intent_with_llm(self, instruction: str) -> IntentAnalysis:
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "你是一个机器人任务规划器。分析用户意图..."
            },
            {"role": "user", "content": instruction}
        ]
    )
    # 解析响应并返回 IntentAnalysis
```

### 2. 添加错误处理

```python
try:
    intent = planner.analyze_intent(instruction)
    result = planner.generate_task_plan(...)
except Exception as e:
    logger.error(f"规划失败: {e}")
    return {"error": str(e), "status": "FAILED"}
```

### 3. 日志和监控

```python
import logging

logger = logging.getLogger(__name__)

# 记录每个规划请求
logger.info(f"规划请求: {instruction}")
logger.info(f"意图: {intent.intent_type} - {intent.primary_action}")
logger.info(f"结果: {result.get('run_id')}")
```

### 4. 性能优化

- 缓存 schema 加载
- 异步处理长耗时的任务规划
- 批量处理多个指令

## 🧪 测试用例集合

### 查询类测试
```python
queries = [
    "系统里有多少台机器人？",
    "现在哪些机器人在线？",
    "机器人电量怎么样？",
    "仓储管理机器人是什么？",
    "有哪些机器人可以巡检？"
]
```

### 任务类测试
```python
tasks = [
    "将货物从仓库搬运到办公室",
    "对仓库进行巡检",
    "去充电器位置充电",
    "拍一张仓库的照片",
    "把这些箱子堆垛到3层高"
]
```

## 📊 性能指标

当前实现的性能：

| 操作 | 耗时 | 说明 |
|------|------|------|
| Schema 加载 | ~10ms | 首次加载 |
| 意图分析 | ~5ms | 关键字匹配 |
| 任务规划 | ~20ms | 单机器人任务 |
| 总响应时间 | ~100ms | 包括 I/O |

## 🐛 常见问题

**Q: 为什么机器人没有选对？**
A: 检查 `_select_robot_for_task()` 中的优先级顺序，或者提供更明确的指令。

**Q: 怎么添加新的动作？**
A: 在 schema 中添加到对应的 `capabilities` 部分，同时在 planner 中添加对应的处理逻辑。

**Q: 支持多机器人协作吗？**
A: 当前支持单机器人任务，多机器人协作可以通过扩展 `llm_global_planning` 来实现。

**Q: 怎么集成自己的机器人状态系统？**
A: 修改 `generate_query_response()` 来调用你的状态 API。

## 📖 更多信息

- 详细 API 文档：见 `LLM_PLANNER_README.md`
- 代码注释：见 `llm_planner.py`
- 测试用例：运行 `python test_llm_planner.py`

