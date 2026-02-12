import time
import requests
import json
from log.logger_config import logger
from enum import Enum

class MotionStatus(Enum):
    IDLE = 0          # 空闲
    START = 1         # 开始执行
    OPERATING = 2     # 运行中
    PAUSE = 3         # 暂停
    STOP = 4          # 停止




class MotionService():
    def __init__(
        self, 
        host: str, 
        mc_service: any,
        motion_list_path="./config/motion-list.json"
    ):
        self._host = host
        self._base_url = f"http://{host}:59001"
        self._base_motion_url = f"http://{host}:56444"
        self._send_motion_command_url = f"{self._base_motion_url}/rpc/aimdk.protocol.MotionCommandService/SendMotionCommand"
        self._mc_service = mc_service
        self._header = {
            "content-type": "application/json",
            "timeout": "60000"
        }
        self._stop_flag = False

        self._motion_list_map = self.load_motion_list(motion_list_path)

    def load_motion_list(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        motion_list_map = {}
        for m in data['motion_list']:
            try:
                motion_list_map[str(m['motion_id'])] = m
            except KeyError as e:
                print(f"数据加载失败: {m} - 错误: {str(e)}")

        return motion_list_map
        


    def getMotionList(self)->any:
        api_url= self._base_url + "/rpc/aimdk.protocol.RcMotionPlayerService/GetMotionList"
        request_json = {}
        resp = requests.post(api_url, json.dumps(request_json), headers=self._header)
        return resp.json()
        # print(resp)
        # print("Status Code:", resp.status_code)
        # print("Response Body:", resp.text)

    def play(self, motion_id: str):
        api_url= self._base_url + "/rpc/aimdk.protocol.RcMotionPlayerService/PlayerMotion"
        timestamp_seconds = int(time.time())
        timestamp_nanos = int(time.time_ns() % 1e9)
        ms_since_epoch = timestamp_seconds * 1000 + timestamp_nanos // 1000000
        logger.info(f"Play motion id: {motion_id}")
        request_json = {
            "header":{
                "timestamp":{
                    "seconds": timestamp_seconds,
                    "nanos": timestamp_nanos,
                    "msSinceEpoch": ms_since_epoch
                }
            },
            "motion_id": motion_id
        }
        resp = requests.post(api_url, json.dumps(request_json), headers=self._header)
        # print(resp)
        # print("Status Code:", resp.status_code)
        print("Response Body:", resp.text)


    def play_path(self, motion_id: int):
        motion_id_str = str(motion_id)

        if motion_id_str not in self._motion_list_map:
            return
        motion = self._motion_list_map[motion_id_str]
        motion_play_path = motion['motion_play_path']
        request_json = {
            "motion_id": motion_play_path,
            "duration_ms": 10000,
            "cmd_end": True,
            "cmd_pause": False,
            "cmd_reset": False
        }
        resp = requests.post(self._send_motion_command_url, json.dumps(request_json), headers=self._header)
        print(resp.json())
        return resp.json()

    def stop(self):
        self._stop_flag = True
        print("stop ...................")


    def play_list(self, motion_list):
        # mc_states = self._mc_service.get_current_action()
        # print("play_list=>mc_states:", mc_states)
        # if mc_states != "McAction_JOINT_FREEZE" and mc_states != "McAction_STAND_ARM_EXT_JOINT_SERVO" and mc_states != "McAction_NAVIGATION_DEFAULT":
        #     return False
        # if not self._mc_service.ensure_action("McAction_STAND_ARM_EXT_JOINT_SERVO"):
        #     return False
        logger.info("Play motion list")
        self._stop_flag = False
        self.reset()
        motion_list_len = len(motion_list)
        i = 0
        j = 0
        for m in motion_list:
            i += 1
            j = 0
            motion_id = m['id']
            self.play(motion_id)
            while True:
                if self._stop_flag:
                    print("motion start stop ...")
                    self.reset()
                    self._stop_flag = False
                    print("motion stop ...")
                    return True
                j += 1
                time.sleep(1)
                if j >= m['userTime']:
                    break
            # time.sleep(m['userTime'])
            if i < motion_list_len:
                self.reset()
        # self.reset()
        print("motion play end ...")
        return True


    def get_motion_info(self):
        api_url= f"{self._base_motion_url}/rpc/aimdk.protocol.MotionCommandService/GetMotionStatus"
        resp = requests.post(api_url, json.dumps({}), headers=self._header)
        result = resp.json()
        print("result: ", result)
        return result

    def get_motion_status(self):
        ret = self.get_motion_info()
        return ret['status']

    def pause(self):
        request_json = {
            "motion_id": "",
            "duration_ms": 10000,
            "cmd_end": True,
            "cmd_pause": True,
            "cmd_reset": False
        }
        resp = requests.post(self._send_motion_command_url, json.dumps(request_json), headers=self._header)

    def reset(self):
        request_json = {
            "motion_id": "",
            "duration_ms": 10000,
            "cmd_end": True,
            "cmd_pause": False,
            "cmd_reset": True
        }
        resp = requests.post(self._send_motion_command_url, json.dumps(request_json), headers=self._header)
    