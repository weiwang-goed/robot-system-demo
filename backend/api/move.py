
import requests
import json
import time
from datetime import datetime


class MoveService():
    def __init__(self, host: str):
        self._session = requests.Session()
        self._session.headers.update({'Content-Type': 'application/json'})
        self._base_url = f"http://{host}:56322"


    def create_header(self):
        now = datetime.utcnow()
        header = {
            "timestamp": {
                "seconds": int(now.timestamp()),
                "nanos": now.microsecond * 1000,
                "ms_since_epoch": int(now.timestamp() * 1000),
            },
            "control_source": "ControlSource_MANUAL"
        }
        return header

    def move_to(self, forward, lateral, angular):
        header = self.create_header()
        
        velocity = {
            "forward_velocity": forward,
            "lateral_velocity": lateral,
            "angular_velocity": angular
        }
        post_data = {
            "header": header,
            "data": velocity
        }
        print("post_data: ", post_data)
        req_url = self._base_url + "/channel/%2Fmotion%2Fcontrol%2Flocomotion_velocity/pb%3Aaimdk.protocol.McLocomotionVelocityChannel"
        res = self._session.post(req_url,json=post_data)
        print(f"Response: {res.status_code} - {res.text}\n")


    def move_foward(self, forward):
        print("###move_foward: ", forward)
        self.move_to(forward, 0, 0)

    def move_lateral(self, lateral):
        print("###move_lateral: ", lateral)
        self.move_to(-0.01, lateral, 0)   # -0.01修正
        # self.move_to(0, lateral, 0)   # -0.01修正

    def move_angular(self, angular):
        print("###move_angular: ", angular)
        self.move_to(0, 0, angular)


