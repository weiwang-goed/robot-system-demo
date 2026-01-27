from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import json
import datetime
from typing import Optional
import logging
import os
import sys
from dotenv import load_dotenv

# Ensure current directory is in Python path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 加载 .env 文件中的环境变量（BAIDU_API_KEY, BAIDU_MODEL 等）
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    logging.getLogger(__name__).info(f"已加载 .env 文件: {env_path}")
else:
    logging.getLogger(__name__).warning(f".env 文件不存在: {env_path}")

# 根据环境变量选择规划器
PLANNER_TYPE = os.getenv("PLANNER_TYPE", "baidu").lower()

if PLANNER_TYPE == "baidu":
    PLANNER_NAME = "百度千帆"

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DEMO_PATH = DATA_DIR / "demo_run.json"
SCHEMA_PATH = DATA_DIR / "robot_behaviors_schema.json"

app = FastAPI(
    title="Robot Planner with LLM",
    description="使用百度千帆的机器人规划系统"
)

# 初始化规划器 - 延迟初始化（在第一次使用时）
planner = None
PLANNER_NAME = "未初始化"

def init_planner():
    """延迟初始化规划器 - 在需要时调用"""
    global planner, PLANNER_NAME
    
    if planner is not None:
        return planner
    
    PLANNER_TYPE = os.getenv("PLANNER_TYPE", "baidu").lower()
    
    # 尝试初始化规划器
    if PLANNER_TYPE == "baidu":
        try:
            from llm_planner_baidu import create_planner
            planner = create_planner(schema_path=SCHEMA_PATH)
            PLANNER_NAME = "百度千帆"
            logger.info(f"规划器初始化成功: {PLANNER_NAME}")
            return planner
        except Exception as e:
            logger.warning(f"百度千帆规划器初始化失败: {e}，尝试 OpenAI")
    
# Allow CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    instruction: str
    site: Optional[str] = None


@app.post("/api/generate_plan")
async def generate_plan(req: GenerateRequest):
    """
    生成机器人任务计划或回答查询
    
    使用 LLM 进行智能规划
    
    工作流程:
    1. 分析用户意图
    2. 根据意图生成响应:
       - 查询: 直接回答问题
       - 任务: 生成机器人任务计划
    3. 保存结果到 demo_run.json
    """
    global planner
    try:
        if not planner:
            planner = init_planner()
        
        if not planner:
            raise HTTPException(
                status_code=500,
                detail="规划器未初始化。请检查 BAIDU_API_KEY 环境变量。"
            )
    except Exception as e:
        logger.error(f"规划器初始化失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"规划器初始化失败: {str(e)}"
        )
    
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
        raise HTTPException(
            status_code=400,
            detail=f"在指定地点 '{site}' 未找到可用机器人" if site else "没有可用的机器人"
        )

    logger.info(f"处理请求: '{instruction}' (可用机器人: {len(avail)})")
    
    try:
        # ============ 使用 LLM Planner ============
        logger.info(f"DEBUG: planner 对象 = {planner}, 类型 = {type(planner)}")
        
        # 第一步：分析用户意图
        logger.info(f"DEBUG: 准备调用 planner.analyze_intent，instruction='{instruction}'，avail={[r.get('id') for r in avail]}")
        intent = planner.analyze_intent(instruction, avail)
        logger.info(f"DEBUG: analyze_intent 返回成功")
        logger.info(f"意图分析: {intent.intent_type} - {intent.primary_action} (置信度: {intent.confidence})")
        
        # 第二步：根据意图类型生成响应
        if intent.intent_type == "query":
            # 信息查询模式 - 直接回答问题
            logger.info("生成查询响应...")
            result = planner.generate_query_response(instruction, avail)
        else:
            # 任务执行模式 - 生成机器人任务计划
            logger.info(f"生成任务计划 ({intent.primary_action})...")
            result = planner.generate_task_plan(instruction, intent, avail, site if site else None)

        # 保存到 demo_run.json
        try:
            DEMO_PATH.write_text(
                json.dumps(result, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8"
            )
            logger.info(f"结果已保存到 {DEMO_PATH}")
        except Exception as e:
            logger.error(f"保存结果失败: {e}")
            # 继续返回结果，即使保存失败
        
        logger.info(f"DEBUG: 返回结果，类型={type(result)}, 键={list(result.keys()) if isinstance(result, dict) else 'N/A'}")
        logger.info(f"DEBUG: 响应摘要 - type={result.get('type')}, status={result.get('status')}")
        return result
    
    except Exception as e:
        logger.error(f"生成计划时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"生成计划失败: {str(e)}"
        )
