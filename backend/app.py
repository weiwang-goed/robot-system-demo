from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import json
import logging
import os
import sys
import copy  # 用于深拷贝计划数据
from typing import Optional
import asyncio
from dotenv import load_dotenv
from typing import List

# Ensure current directory is in Python path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 加载 .env 文件中的环境变量
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    logging.getLogger(__name__).info(f"已加载 .env 文件: {env_path}")
else:
    logging.getLogger(__name__).warning(f".env 文件不存在: {env_path}")

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class _SuppressPathFilter(logging.Filter):
    """Suppress noisy access log entries for specific request paths."""
    def __init__(self, *paths: str):
        super().__init__()
        self._paths = tuple(paths)

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(f'"GET {path} ' in message for path in self._paths)

logging.getLogger("uvicorn.access").addFilter(_SuppressPathFilter("/agv/getState"))

# 路径配置
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DEMO_PATH = DATA_DIR / "demo_run.json"
SCHEMA_PATH = DATA_DIR / "robot_behaviors_schema.json"


# =============================================================
# [关键整合点 1] 引入并初始化 RobotExecutor
# =============================================================
ROBOT_IP = os.getenv("ROBOT_IP", "127.0.0.1") # 可以从环境变量读取，默认 192.168.1.100
global_executor = None

try:
    from robot_executor import RobotExecutor
    logger.info("成功导入 RobotExecutor 类")
    
    # 尝试初始化全局执行器
    try:
        global_executor = RobotExecutor(robot_ip=ROBOT_IP)
        logger.info(f"全局执行器 (global_executor) 初始化成功，目标 IP: {ROBOT_IP}")
    except Exception as init_e:
        logger.error(f"执行器实例化失败: {init_e}")

except ImportError as e:
    logger.error(f"无法导入 RobotExecutor (可能是文件缺失): {e}")
    RobotExecutor = None


# FastAPI App 定义
app = FastAPI(
    title="Robot Planner with LLM",
    description="使用百度千帆的机器人规划系统"
)

# 初始化规划器 - 延迟初始化
planner = None
PLANNER_NAME = "未初始化"

def init_planner():
    """延迟初始化规划器"""
    global planner, PLANNER_NAME
    
    if planner is not None:
        return planner
    
    PLANNER_TYPE = os.getenv("PLANNER_TYPE", "baidu").lower()
    
    if PLANNER_TYPE == "baidu":
        try:
            from llm_planner_baidu import create_planner
            planner = create_planner(schema_path=SCHEMA_PATH)
            PLANNER_NAME = "百度千帆"
            logger.info(f"规划器初始化成功: {PLANNER_NAME}")
            return planner
        except Exception as e:
            logger.warning(f"百度千帆规划器初始化失败: {e}")
            return None

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


        

# =============================================================
# 接口定义
# =============================================================

class ExecuteRequest(BaseModel):
    plan: dict

@app.post("/api/face_detected")
async def handle_face_detected(
    background_tasks: BackgroundTasks,
    usernames: List[str] = Query(None)
):
    logger.info(f"接收到人脸信号: {usernames}")
    
    # 业务逻辑
    if not global_executor:
        return {"status": "error", "message": "Executor not initialized"}
    
    speech_text = getattr(global_executor, "cached_speech_text", None)
    targets = getattr(global_executor, "targets", None)

    logger.info(f"speech_text {speech_text}")
    logger.info(f"targets {targets}")
    logger.info(f"usernames: {usernames}")


    if not speech_text or not targets:
        logger.warning("--- 没有缓存 ---")
        return {"status": "ignored", "message": "No cache"}
    

    for i in targets:
        if i in usernames:

            background_tasks.add_task(global_executor.handle_speech, speech_text)
            break
    
    return {
        "status": "success",
        "userId": usernames,
        "targets": targets
    }



class GenerateRequest(BaseModel):
    instruction: str
    site: Optional[str] = None

@app.post("/api/generate_plan")
async def generate_plan(req: GenerateRequest):
    """
    生成机器人任务计划或回答查询
    """
    global planner
    try:
        if not planner:
            planner = init_planner()
        
        if not planner:
            raise HTTPException(status_code=500, detail="规划器未初始化。")
    except Exception as e:
        logger.error(f"规划器初始化失败: {e}")
        raise HTTPException(status_code=500, detail=f"规划器初始化失败: {str(e)}")
    

    # 加载机器人数据
    robots_path = Path(__file__).resolve().parents[1] / "data" / "robots.json"
    if not robots_path.exists():
        raise HTTPException(status_code=500, detail="robots.json 文件未找到")

    robots = json.loads(robots_path.read_text(encoding="utf-8"))
    site = req.site or ""
    instruction = req.instruction or ""
    
    if not instruction:
        raise HTTPException(status_code=400, detail="instruction 不能为空")
    
    # 过滤机器人
    if site:
        avail = [r for r in robots if r.get("site") == site]
    else:
        avail = robots

    if not avail:
        raise HTTPException(status_code=400, detail=f"在指定地点 '{site}' 未找到可用机器人")

    logger.info(f"处理请求: '{instruction}'")
    
    try:
        # 1. 意图分析
        intent = planner.analyze_intent(instruction, avail)
        logger.info(f"意图分析: {intent.intent_type} - {intent.primary_action}")
        
        # 2. 生成响应
        if intent.intent_type == "query":
            result = planner.generate_query_response(instruction, avail)
        else:
            result = planner.generate_task_plan(instruction, intent, avail, site if site else None)

        # 3. 保存结果
        try:
            DEMO_PATH.write_text(
                json.dumps(result, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"保存结果失败: {e}")
        
        return result
    
    except Exception as e:
        logger.error(f"生成计划时出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成计划失败: {str(e)}")



@app.post("/api/execute_plan")
async def execute_full_plan(request: ExecuteRequest, background_tasks: BackgroundTasks):
    """
    【全功能执行模式】
    数据来源：与语音测试一样，直接使用前端传来的 request.plan
    行为：不做任何过滤，执行所有任务（导航、搜索、语音）。
    """
    if not global_executor:
        raise HTTPException(
            status_code=500, 
            detail="机器人执行器未初始化"
        )

    # 1. 核心：直接拿数据
    origin_plan = request.plan
    run_id = origin_plan.get("run_id", "unknown")
    
    logger.info(f"🚀 收到全功能执行请求 RunID: {run_id} - 准备执行所有任务")

    # 2. 核心
    background_tasks.add_task(global_executor.execute_plan, origin_plan)

    return {
        "status": "started",
        "message": f"全任务流程已启动 (RunID: {run_id})，机器人即将开始运动！",
        "plan_preview": origin_plan
    }












# =============================================================
# 仅测试语音的接口 (架上调试专用)
# =============================================================



@app.post("/api/test_speech_only")
async def execute_speech_only(request: ExecuteRequest, background_tasks: BackgroundTasks):
    """
    接收任务计划，但过滤掉所有运动指令，仅执行语音播报。
    适用于机器人在架子上调试。
    """
    if not global_executor:
        raise HTTPException(
            status_code=500, 
            detail="机器人执行器未初始化。请检查 robot_executor.py 是否存在以及 IP 配置。"
        )

    origin_plan = request.plan
    run_id = origin_plan.get("run_id", "unknown")
    logger.info(f"收到语音测试请求 RunID: {run_id}")

    # --- 核心过滤逻辑 ---
    # 1. 深拷贝一份计划，以免修改原始数据
    safe_plan = copy.deepcopy(origin_plan)
    
    tool_calls = safe_plan.get("robot_tool_calls", {})
    task_count = 0
    
    for robot_id, actions in tool_calls.items():
        # 过滤列表：只保留 action == 'speech_synthesis'
        safe_actions = [
            action for action in actions 
            if action.get("action") == "speech_synthesis"
        ]
        
        # 替换原有的动作列表，删掉导航任务
        tool_calls[robot_id] = safe_actions
        task_count += len(safe_actions)
        
        # 打印日志方便调试
        if safe_actions:
            texts = [a['arguments'].get('text', '')[:10] + '...' for a in safe_actions]
            logger.info(f"机器人 {robot_id} 保留语音任务: {texts}")
        else:
            logger.warning(f"机器人 {robot_id} 没有语音任务，将不执行任何操作")

    if task_count == 0:
        return {"status": "skipped", "message": "计划中没有包含语音任务 (speech_synthesis)"}

    # --- 提交给执行器 ---
    # 执行器在后台运行，不会阻塞 API
    background_tasks.add_task(global_executor.execute_plan, safe_plan)

    return {
        "status": "started",
        "message": f"已启动安全模式执行，共调度 {task_count} 个语音任务",
        "filtered_plan_preview": safe_plan # 返回给前端看看过滤后的样子
    }
