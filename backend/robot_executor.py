import time
import logging
import requests
import json
from typing import Dict, Any

from api.navigation import NavigationService
from api.motion_control_service import MotionControlService
from api.tts_to_voice import TtsVoice


logger = logging.getLogger(__name__)


class RobotExecutor:
    def __init__(self, robot_ip: str = "127.0.0.1"):
        self.robot_ip = robot_ip
        # 导航相关服务统一使用 53176 端口
        self.nav_base_url = f"http://{robot_ip}:53176"
        
        # 地图 ID
        self.current_map_id = 1767068974292 
        
        logger.info(f"🤖 初始化 RobotExecutor, 连接目标: {robot_ip}")

        self.tts_service = TtsVoice(host=robot_ip) if TtsVoice else None
        
        # 初始化导航驱动 (仅用于复位，发送指令我们用 requests)
        self.mc_service = MotionControlService(host=robot_ip) if MotionControlService else None
        if NavigationService and self.mc_service:
            try:
                self.nav_driver = NavigationService(robot_ip, self.current_map_id, self.mc_service)
                # 启动时先 Cancel 一次，防止上次任务残留
                logger.info("🔄 正在复位导航状态 (set_cancel)...")
                try: self.nav_driver.set_cancel() 
                except: pass 
                time.sleep(0.5)
            except:
                self.nav_driver = None

    def execute_plan(self, plan_data: Dict[str, Any]):
        run_id = plan_data.get('run_id', 'unknown')
        logger.info(f"🚀 开始执行任务流: {run_id}")
        
        tool_calls = plan_data.get("robot_tool_calls", {})
        
        # 遍历执行每一个机器人的任务
        for robot_id, actions in tool_calls.items():
            
            # 依然保留排序逻辑，确保 搜索/导航 优于 返航
            # 虽然语音不在这里执行了，但保持排序逻辑可以防止 future bugs
            def get_action_priority(act):
                atype = act.get("action", "")
                if atype == "return_to_location":
                    return 100
                elif atype == "speech_synthesis":
                    return 1
                else:
                    return 50
            
            actions.sort(key=get_action_priority)
            
            for step_index, action_data in enumerate(actions):
                if action_data.get("status") == "completed": continue
                
                action_type = action_data.get("action")
                args = action_data.get("arguments", {})
                

                if action_type == "speech_synthesis":
                    text = args.get("text") or args.get("message")
                    if text:
                        self.cached_speech_text = text
                        logger.info(f"✅ 缓存语音信息{text}")

                    recipients = args.get("recipients")
                    if recipients:
                        self.targets = recipients
                        logger.info(f"✅ 缓存目标人名{recipients}")
                    continue

                # 标记状态为运行中
                action_data["status"] = "running"
                logger.info(f"--- [步骤 {step_index + 1}] 执行: {action_type} ---")
                
                success = True
                if action_type == "search_people":
                    success = self._handle_search(args)
                elif action_type == "navigate":
                    success = self._handle_navigation(args)
                elif action_type == "return_to_location":
                    success = self._handle_navigation(args)
                
                # 注意：这里不再有 elif action_type == "speech_synthesis"
                
                action_data["status"] = "completed" if success else "failed"
                
                if not success:
                    logger.error("❌ 关键运动任务失败，中断任务链")
                    break
        
        self.cached_speech_text = None
        self.targets = None
        
        logger.info("✅ 运动任务流执行完毕")

        return plan_data

    # ======================================================
    # 动作逻辑实现
    # ======================================================

    def _handle_navigation(self, args: Dict) -> bool:
        """
        [像素级复刻 Bash] 单点导航逻辑
        """
        # 1. 解析目标点
        target_raw = args.get("location_id") or args.get("target_id") or args.get("location")
        if not target_raw: return False
        try: target_int = int(target_raw) 
        except: return False

        # 2. 定义 URL
        url = f"{self.nav_base_url}/rpc/aimdk.protocol.PncService/PlanningNaviToGoal"
        
        # 3. 定义 Headers
        headers = {
            "Content-Type": "application/json",
            "timeout": "60000",
            "Connection": "close"
        }

        # === 核心逻辑：自动重试 + 动态 ID ===
        for attempt in range(3):
            # 【关键】生成动态 Task ID
            current_task_id = f"{int(time.time() * 1000)}"
            
            # 4. 构造 Body
            payload = {
                "header": {
                    "timestamp": {
                        "seconds": 0,
                        "nanos": 0,
                        "ms_since_epoch": 0
                    },
                    "control_source": 0
                },
                "task_id": current_task_id,     
                "map_id": 1767068974292,
                "target_id": target_int,        
                "guide_line_id": 0,
                "ackerman_mode": False          
            }

            logger.info(f"🚗 [Attempt {attempt+1}] 发送导航请求 -> {target_int}")
            
            try:
                # 使用 json.dumps 确保格式严格
                resp = requests.post(url, data=json.dumps(payload), headers=headers, timeout=5)
                
                # --- 成功 ---
                if resp.status_code == 200:
                    logger.info("✅ 指令发送成功")
                    # 这里必须保留等待，确保机器人内部状态切换，否则查状态可能查到上一次的Success
                    logger.info("💤 起步防抖 (等待 3s)...")
                    time.sleep(3) 
                    
                    # 进入阻塞监控状态
                    return self._block_until_arrival()
                
                else:
                    logger.error(f"❌ 错误: {resp.status_code} - {resp.text}")
                    return False

            except Exception as e:
                logger.error(f"❌ 网络异常: {e}")
                return False
        
        return False

    def _handle_search(self, args: Dict) -> bool:
        """
        多点巡逻：到点 -> 停5秒 -> 说话 -> 下一点
        """
        target_ids = args.get("target_ids") or args.get("targets", [])
        message = args.get("message") or "我已到达巡逻点位，正在检测周边环境。"
        
        if not target_ids: 
            single_id = args.get("location_id")
            if single_id: target_ids = [single_id]
            else: return True

        logger.info(f"🔍 启动巡逻链，点位: {target_ids}")

        for index, tid in enumerate(target_ids):
            logger.info(f"👉 [第 {index+1}/{len(target_ids)} 站] 前往: {tid}")
            
            # 1. 走过去 (会阻塞直到到达)
            if not self._handle_navigation({"location_id": tid}):
                logger.error(f"❌ 无法到达 {tid}，跳过或中断")
                return False
            
            # 2. 到达后：停 5 秒
            logger.info(f"👀 到达 {tid}，停留 5 秒...")
            time.sleep(5) # 修正为 5 秒，原代码是 10 秒
            
            # 3. 说话
            logger.info(f"🗣️ 播报: {message}")
            if self.tts_service:
                full_text = f"到达{tid}号点。{message}"
                try: 
                    self.tts_service.text_to_voice_sync(full_text)
                except: 
                    pass
            
        return True

    def handle_speech(self, args: str) -> bool:
        text = args
        if self.tts_service and text:
            try: 
                self.tts_service.text_to_voice_sync(text)
            except: 
                pass
        return True

    def _block_until_arrival(self) -> bool:
        """ 
        [改进版] 轮询 ActionGetState 接口阻塞线程，直到任务状态变为 SUCCESS 或 FAILED。
        对应 Bash 命令:
        curl -X POST "http://IP:53176/rpc/aimdk.protocol.PncService/ActionGetState" -d '{"task_id": 0}'
        """
        
        # 使用 PncService 接口，与 _handle_navigation 相同的 Base URL
        url = f"{self.nav_base_url}/rpc/aimdk.protocol.PncService/ActionGetState"
        headers = {"Content-Type": "application/json", "Connection": "close"}
        
        # task_id: 0 代表查询最近一次任务的状态
        payload = {"task_id": 0}

        logger.info("⏳ [闭环监控] 正在监控导航状态 (ActionGetState)...")
        
        start_time = time.time()
        
        while True:
            try:
                # 发送请求
                resp = requests.post(url, json=payload, headers=headers, timeout=2)
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    # 获取状态字符串，例如 "PncServiceState_RUNNING"
                    state = data.get("state", "UNKNOWN")
                    task_id_resp = data.get("task_id", "unknown")
                    
                    # 打印 debug 日志 (过于频繁可以注释掉)
                    # logger.info(f"📡 任务 {task_id_resp} 状态: {state}")

                    # === 判定逻辑 ===
                    if state == "PncServiceState_SUCCESS":
                        logger.info(f"✅ 导航成功到达！(Task: {task_id_resp})")
                        return True
                    
                    elif state == "PncServiceState_FAILED":
                        logger.warning(f"❌ 导航任务失败 (Task: {task_id_resp})")
                        return False
                    
                    elif state == "PncServiceState_RUNNING":
                        # 正在跑，继续循环
                        pass
                        
                    elif state == "PncServiceState_IDLE":
                        # 闲置状态。
                        # 注意：如果刚下发任务，可能短暂处于 IDLE，
                        # 但我们在 _handle_navigation 里已经 sleep(3) 了，所以这里遇到 IDLE 更有可能是任务被取消或未开始。
                        # 暂时视为继续等待，或根据业务需求决定是否退出。
                        if time.time() - start_time > 10:
                            logger.warning("⚠️ 任务长期处于 IDLE 状态，判定为未执行")
                            return False
                    else:
                        logger.info(f"📡 机器人状态: {state}")

                else:
                    logger.warning(f"⚠️ 状态查询非200: {resp.status_code}")

            except Exception as e:
                logger.warning(f"⚠️ 监控网络波动: {e}")
            
            # 超时保护 (5分钟)
            if time.time() - start_time > 300:
                logger.error("❌ 导航严重超时 (5分钟)，强制结束")
                return False
            
            # 轮询间隔 1 秒
            time.sleep(1)