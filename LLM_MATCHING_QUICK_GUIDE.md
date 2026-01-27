# LLM 驱动模板匹配 - 快速参考

## 核心改变总结

| 项目 | 原来 | 现在 |
|------|------|------|
| **匹配方式** | 规则匹配（正则表达式） | LLM 智能匹配（qwen3-8b） |
| **参数提取** | 硬编码规则 | LLM 自动提取（JSON格式） |
| **模型** | N/A | qwen3-8b（轻量高效） |
| **置信度** | 无 | 返回 0.0-1.0 的置信度 |
| **参数返回** | 部分参数 | **完整 JSON 格式参数** |

---

## 关键代码变化

### 1. 模板匹配（task_templates.py）

**之前（规则匹配）：**
```python
template = find_matching_template(instruction)  # 正则匹配
if template:
    params = template.extract_params(instruction)  # 硬编码提取
```

**现在（LLM 匹配）：**
```python
result = engine.apply_template(instruction)  # LLM 调用
# 返回：
{
    "template_name": "notification",
    "matched": True,
    "confidence": 0.95,
    "params": {"recipients": [...], "location": "..."}
}
```

### 2. 任务规划（llm_planner_baidu.py）

**流程改变：**
```
原来：
  模板匹配 (OK) → 使用模板任务序列
              (NO) → LLM 规划

现在：
  LLM 匹配 + 参数提取
         ↓
  置信度 > 0.5? 
         ├─ YES → 使用模板任务序列
         └─ NO  → LLM 直接规划（返回 JSON 参数）
```

**返回格式现在包含：**
```json
{
  "model": "llm-template-matching",
  "template_confidence": 0.95,
  "params": {...},                    // 模板参数
  "parameters": {...},                // LLM 提取的额外参数（新增）
  "llm_global_planning": [...],
  "robot_tool_calls": {...}
}
```

---

## 环境配置

**关键环境变量：**

```bash
# 模板匹配模型（轻量级）
INTENT_MODEL=qwen3-8b

# 直接规划模型（高性能）
PLANNING_MODEL=ernie-4.5-21b-a3b-thinking

# API 密钥
BAIDU_API_KEY=your-key-here
```

所有配置都在 `backend/.env` 中

---

## API 示例

### 请求：
```bash
POST /api/generate_plan
{
  "instruction": "通知李涛和吴晋来2215开会",
  "site": "building-A"
}
```

### 响应（示例）：
```json
{
  "run_id": "run_1706335200000",
  "status": "PLANNING",
  "task_type": "navigate",
  "instruction": "通知李涛和吴晋来2215开会",
  "timestamp": "2026-01-27T12:00:00Z",
  "model": "llm-template-matching",
  
  "template_used": "notification",
  "template_confidence": 0.95,
  
  "params": {
    "recipients": ["李涛", "吴晋"],
    "location": "2215",
    "reason": "开会"
  },
  
  "parameters": {
    "extracted_params": {...}
  },
  
  "llm_global_planning": [
    {
      "task_order": 0,
      "robot_id": "QR-SZZX-0001",
      "task": "通知任务",
      "description": "通知 李涛、吴晋 到 2215 开会"
    }
  ],
  
  "robot_tool_calls": {
    "QR-SZZX-0001": [
      {"action": "search_person", "arguments": {...}},
      {"action": "navigation", "arguments": {...}},
      {"action": "speech_synthesis", "arguments": {...}}
    ]
  },
  
  "constraints": [
    "使用 LLM 匹配的 notification 模板",
    "参数已通过 LLM 提取"
  ]
}
```

---

## 模板类型

当前支持的模板（LLM 自动识别）：

1. **notification** - 通知任务
   - 参数: `recipients`, `location`, `reason`
   - 例: "通知李涛和吴晋来2215开会"

2. **inspection** - 巡检任务
   - 参数: `area`, `take_photo`, `inspection_type`
   - 例: "巡视一楼并拍照检查"

3. **transport** - 运输任务
   - 参数: `item`, `source`, `destination`
   - 例: "把物料运送到仓库"

4. **general** - 通用任务
   - 自动识别其他类型的任务

---

## 如何测试

```bash
# 进入后端目录
cd backend

# 运行测试脚本
python test_llm_matching.py

# 输出将显示：
# ✓ 模板匹配结果
# ✓ 参数提取内容
# ✓ 置信度评分
# ✓ 完整的规划流程
```

---

## 置信度解读

| 置信度 | 含义 | 处理方式 |
|--------|------|---------|
| > 0.8 | 非常确信 | 直接使用模板 |
| 0.5-0.8 | 较为确信 | 使用模板 |
| < 0.5 | 不确信 | 转向高性能 LLM 直接规划 |
| N/A | 无法识别 | 使用 LLM 直接规划 |

---

## 故障排查

### 问题：模板一直匹配失败

**解决：**
1. 检查 `BAIDU_API_KEY` 是否正确设置
2. 检查网络连接是否正常
3. 运行 `test_llm_matching.py` 查看详细错误

### 问题：参数提取不完整

**解决：**
1. 指令表述可能不清晰，尝试更具体的表述
2. 调整 `INTENT_TEMPERATURE` 值（降低 = 更准确，升高 = 更创意）
3. 检查模板定义是否包含该参数字段

### 问题：LLM 响应超时

**解决：**
1. 检查网络延迟
2. 降低 `INTENT_TOP_P` 值减少生成复杂度
3. 检查是否有其他进程占用 API 配额

---

## 性能指标

- **模板匹配** (qwen3-8b): ~1-2 秒
- **参数提取**: 与匹配同步
- **LLM 直接规划** (ernie-4.5): ~2-3 秒
- **缓存命中**: 立即（如果启用缓存）

---

## 向后兼容性

✅ **完全兼容现有 API**

新增的字段：
- `template_confidence` - 可以安全忽略
- `parameters` - 可以安全忽略

原有字段都被保留：
- `llm_global_planning` ✓
- `robot_tool_calls` ✓
- `constraints` ✓

---

## 联系与支持

如有问题，请查看：
- [详细修改说明](LLM_MATCHING_CHANGES.md)
- [测试脚本](backend/test_llm_matching.py)
- [环境配置](backend/.env)
