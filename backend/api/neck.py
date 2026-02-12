import time
import requests
import json
from datetime import datetime


# curl -i     -H 'content-type:application/json' \
#             -H 'timeout: 1000' \
#             -X POST 'http://192.168.100.100:56444/rpc/aimdk.protocol.MotionCommandService/DisableMotionPlayer' \
#             -d '{}'

# curl -i     -H 'content-type:application/json' \
#             -H 'timeout: 1000' \
#             -X POST 'http://192.168.100.100:56444/rpc/aimdk.protocol.MotionCommandService/EnableMotionPlayer' \
#             -d '{}'


class NeckService():
    def __init__(self, host: str):
        self._host = host
        self._base_url = f"http://{host}:56322"

        self._headers = {"Content-Type": "application/json", "timeout": "60000"}
        self._session = requests.Session()
        self._session.headers.update(self._headers)

    def motion_player_switch(self, status):
        switch = 'EnableMotionPlayer'
        if status == "disable":
            switch = 'DisableMotionPlayer'
        req_url = f"http://{self._host}:56444/rpc/aimdk.protocol.MotionCommandService/{switch}"
        print("motion_player_switch=>req_url: ", req_url)
        resp = requests.post(req_url, json.dumps({}), headers=self._headers)
        print("motion_player_switch=>resp: ", resp.json())
        # self._session.post(req_url, json={})


    def create_header(self):
        now = datetime.utcnow()
        header = {
            "timestamp": {
                "seconds": int(now.timestamp()),
                "nanos": now.microsecond * 1000,
                "ms_since_epoch": int(now.timestamp() * 1000),
            },
            "control_source": "ControlSource_SAFE",
        }
        return header
    def play(self, shake=0.0, nod=0.0):
        self.motion_player_switch('disable')
        time.sleep(0.5)
        req_url = f'{self._base_url}/rpc/aimdk.protocol.McMotionService/SetNeckCommand'
        neck_data = {
            "shake": {
                "name": "idx27_head_joint1",
                "position": shake,
                "velocity": 0.0,
                "effort": 0.0,
            },
            "nod": {
                "name": "idx28_head_joint2",
                "position": nod,
                "velocity": 0.0,
                "effort": 0.0,
            },
        }
        print(f"req_url: {req_url}")
        payload = {"header": self.create_header(), "data": neck_data}
        print(f"payload: {payload}")
        response = self._session.post(req_url, json=payload)
        print(f"response: {response.json()}")
        return response

    def reset(self):
        self.play(0,0)
        time.sleep(1)
        self.motion_player_switch('enable')

if __name__ == '__main__':
    pass
