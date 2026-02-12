
import base64
import json
import uuid
import requests


class TtsHs():
    def __init__(self):
        self._appid = "4796355179"
        self._uid = "2102314534"
        self._access_token= "O6016MagZtsS24_Cr12jmKYiNn6UVPdt"
        self._api_url = "https://openspeech.bytedance.com/api/v1/tts"
        self._voice_type = "BV406_V2_streaming"
        self._cluster = "volcano_tts"
        self._header = {"Authorization": f"Bearer;{self._access_token}"}

    def request_gen(self, text: str):
        request_json = {
            "app": {
                "appid": self._appid,
                "token": self._access_token,
                "cluster": self._cluster
            },
            "user": {
                "uid": self._uid
            },
            "audio": {
                "voice_type": self._voice_type,
                "encoding": "wav",
                # "speed_ratio": 1.0,
                "speed": 10,
                # "volume_ratio": 1.0,
                'volume': 10,
                'rate': 16000,
                # "pitch_ratio": 1.0,
                'pitch': 10,
            },
            "request": {
                "reqid": str(uuid.uuid4()),
                "text": text,
                "text_type": "plain",
                "operation": "query",
                "with_frontend": 1,
                "frontend_type": "unitTson"

            }
        }
        return json.dumps(request_json)

    def text_to_voice(self, text: str) -> str:
        try:
            resp = requests.post(self._api_url, self.request_gen(text), headers=self._header)
            # print(f"resp body: \n{resp.json()}")
            if "data" in resp.json():
                data = resp.json()["data"]
                # print("data: ", data)
                # print("data type: ", type(data))
                # file_to_save = open("test_submit.wav", "wb")
                # file_to_save.write(base64.b64decode(data))
                return base64.b64decode(data) # data
            return ''
        except Exception as e:
            e.with_traceback()