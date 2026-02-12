import requests
import json
from enum import Enum
import time
import uuid
from log.logger_config import logger
import api.map_service as map_service

# 任务状态量

class NavigationState(Enum):
    UNDEFINED = 0                   # 未知状态，可不做处理;
    IDLE = 1                        # 任务空闲中
    RUNNING = 2                     # 任务运行中
    PAUSING = 3                     # 任务暂停中
    SUCCESS = 4                     # 任务完成
    FAILED = 5                      # 任务失败




class NavigationCommand(Enum):
    UNDEFINED = 0                   # 未知指令，不做处理
    PAUSE = 1                       # 临时停车（导航状态进入 PAUSING 状态）;
    RESUME = 2                      # 继续巡航（导航状态恢复 RUNNING 状态）;
    CANCEL = 3                      # 停车，并终止当前的任务（导航状态回到 IDLE 状态）;

class NavigationService():
    def __init__(self, base_url: str, map_id: any, mc_service: any, gait_rl: bool=False):
        self._map_id = map_id
        self._base_url = f"http://{base_url}:53176"
        self._mc_service = mc_service
        self._gait_rl = gait_rl
        self._header = {
            "content-type": "application/json",
            "timeout": "60000"
        }

        self._session = requests.Session()
        self._session.headers.update({
            'Content-Type': 'application/json',
            "timeout": "60000"
        })

        self._map_service = map_service.MapService(base_url)
        self._task_id = None

    def verify_map_info(self) -> bool:
        map_id = self._map_service.get_current_working_map()
        if map_id != self._map_id:
            print("The map id does not match the current map")
            return False
        return True


    def get_navigation_state(self, task_id)->any:
        req_url = self._base_url + "/rpc/aimdk.protocol.PncService/ActionGetState"
        request_json = {
            "header": {
            "timestamp": {"seconds": 0, "nanos": 0, "ms_since_epoch": 0},
            "control_source": 0,
            },
            "task_id": task_id,
        }
        resp = requests.post(req_url, json.dumps(request_json), headers=self._header)
        # resp = self._session.post(req_url,json=request_json)
        resp.raise_for_status()
        return resp.json()['state']


    def set_navigation_task(self, point_id: int)->any:
        logger.info(f"Set navigation task, map id: {self._map_id} point id: {point_id}")
        req_url = self._base_url + "/rpc/aimdk.protocol.PncService/PlanningNaviToGoal"
        request_json = {
            "header": {
                "timestamp": {"seconds": 0, "nanos": 0, "ms_since_epoch": 0},
                "control_source": 0,
            },
            "task_id": "123456",
            "map_id": self._map_id,
            "target_id": point_id,
            "guide_line_id": 0,
            "ackerman_mode": False,
        }

        resp = requests.post(req_url, json.dumps(request_json), headers=self._header)

        # resp = self._session.post(req_url,json=request_json)
        # print(resp)
        # print(resp.json())
        res_data = resp.json()
        logger.info(f"Set navigation task return: {res_data}")
        self._task_id = res_data['task_id']
        logger.info(f"Set navigation task, task id: {self._task_id}")
        return res_data['task_id']


    def check_is_arrived(self, task_id)->bool:
        while True:
            time.sleep(1)
            navigation_states = self.get_navigation_state(task_id)
            logger.info(f"Current task id:{task_id} - navigation states: {navigation_states}")
            if navigation_states == "PncServiceState_SUCCESS" or navigation_states == "PncServiceState_UNDEFINED" or navigation_states == "PncServiceState_IDLE":
                logger.info(f"Navigation task success")
                time.sleep(1)
                return True
            # if navigation_states == NavigationState.PAUSING.value or navigation_states == NavigationState.ABNORMAL.value


    def move_to(self, point_id: int)->bool:
        # navigation_states = self.get_navigation_state()
        # logger.info(f"Current navigation states: {navigation_states}")
        # if (navigation_states != NavigationState.IDLE.value and navigation_states != NavigationState.ARRIVED.value and navigation_states != NavigationState.UNDEFINED.value):
        #     return False

        mc_states = self._mc_service.get_current_action()
        logger.info(f"Current mc states: {mc_states}")

        # RL_LOCOMOTION_DEFAULT
        # McAction_RL_LOCOMOTION_DEFAULT
        # McAction_RL_LOCOMOTION_ARM_EXT_JOINT_SERVO

        if self._gait_rl:# 强化步态 
            if mc_states != "McAction_RL_LOCOMOTION_ARM_EXT_JOINT_SERVO" and mc_states != "McAction_RL_LOCOMOTION_DEFAULT":
                return False

            if not self._mc_service.ensure_action("McAction_RL_LOCOMOTION_DEFAULT",2,1):
                logger.info("Set mc action McAction_RL_LOCOMOTION_DEFAULT fail")
                return False
        else: # 传统步态
            if mc_states != "McAction_JOINT_FREEZE" and mc_states != "McAction_STAND_ARM_EXT_JOINT_SERVO" and mc_states != "McAction_NAVIGATION_DEFAULT":
                return False

            if not self._mc_service.ensure_action("McAction_NAVIGATION_DEFAULT",2,1):
                logger.info("Set mc action McAction_NAVIGATION_DEFAULT fail")
                return False

        task_id =  self.set_navigation_task(point_id)
        self.check_is_arrived(task_id)


        return True

    def set_navigation_command(self, cmd: int)->bool:
        req_url = self._base_url + "/rpc/planning_msgs/srv/SetNavigationCommand"
        request_json = {
            "command": cmd,
        }
        resp = requests.post(req_url, json.dumps(request_json), headers=self._header)
        # resp = self._session.post(req_url,json=request_json)
        res_data = resp.json()
        return res_data['status']


    def set_pause(self):
        if not self._task_id:
            return
        req_url = self._base_url + "/rpc/aimdk.protocol.PncService/ActionPause"
        request_json = {
            "header": {
                "timestamp": {"seconds": 0, "nanos": 0, "ms_since_epoch": 0},
                "control_source": 0,
            },
            "task_id": self._task_id,
        }

        resp = requests.post(req_url, json.dumps(request_json), headers=self._header)

    def set_resume(self):
        if not self._task_id:
            return
        req_url = self._base_url + "/rpc/aimdk.protocol.PncService/ActionResume"
        request_json = {
            "header": {
                "timestamp": {"seconds": 0, "nanos": 0, "ms_since_epoch": 0},
                "control_source": 0,
            },
            "task_id": self._task_id,
        }

        resp = requests.post(req_url, json.dumps(request_json), headers=self._header)

    def set_cancel(self):
        self._task_id = "123456"
        if not self._task_id:
            return
        req_url = self._base_url + "/rpc/aimdk.protocol.PncService/ActionCancel"
        request_json = {
            "header": {
                "timestamp": {"seconds": 0, "nanos": 0, "ms_since_epoch": 0},
                "control_source": 0,
            },
            "task_id": self._task_id,
        }

        resp = requests.post(req_url, json.dumps(request_json), headers=self._header)


# #!/bin/bash
# # 下发导航任务（以带目标点 id的普通导航为例）
# source {YOUR_PATH}/aimdk_msgs/local_setup.bash

# ros2 service call /planning_msgs/srv/SetNavigationTask aimdk_msgs/srv/SetNavigationTask "header:
#   stamp:
#     sec: 0
#     nanosec: 0
#   frame_id: ''
# map_id: 1732275337238
# type: 1
# target_id: 10
# guide_line_id: 0
# x: 0.0
# y: 0.0
# angle: 0.0"
