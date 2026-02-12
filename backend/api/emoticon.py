import time
import requests
import json


class EmoticonService():
    def __init__(self, host: str, emoticon_enable: bool=True):
        self._base_url = f"http://{host}:59001"
        self._header = {
            "content-type": "application/json",
            "timeout": "60000"
        }
        self._emoticon_enable = emoticon_enable
        self._emoticon_list = self.get_emoticon_list()


    def get_emoticon_list(self)->any:
        # api_url= self._base_url + "/rpc/aimdk.protocol.RcEmoticonPlayerService/GetEmotionList"
        api_url= "http://127.0.0.1:51049/rpc/aimdk.protocol.ResourceService/GetEmoticon"
        resp = requests.post(api_url, json.dumps({}), headers=self._header)
        # print(resp)
        res = resp.json()
        emoticon_list = res['emoticons']
        print(emoticon_list)
        return emoticon_list

    def play_with_name(self, emoticon_name: str):
        result = list(filter(lambda x: x["emoticon_name"] == emoticon_name, self._emoticon_list))
        if result:
            self.play(result[0]['emoticon_id'])

    def play(self, emoticon_id: int):
        api_url= self._base_url + "/rpc/aimdk.protocol.RcEmoticonPlayerService/PlayerEmoticon"
        timestamp_seconds = int(time.time())
        timestamp_nanos = int(time.time_ns() % 1e9)
        ms_since_epoch = timestamp_seconds * 1000 + timestamp_nanos // 1000000

        request_json = {
            "header":{
                "timestamp":{
                    "seconds": timestamp_seconds,
                    "nanos": timestamp_nanos,
                    "msSinceEpoch": ms_since_epoch
                }
            },
            "emoticon_id": emoticon_id,
            "is_need_data": False
        }

        resp = requests.post(api_url, json.dumps(request_json), headers=self._header)
        print(resp)
        print(resp.json())

    def play_list(self, emoticon_list):
        for m in emoticon_list:
            emoticon_id = m['id']
            self.play(emoticon_id)
            time.sleep(m['userTime'])

if __name__ == '__main__':
    emo_service = EmoticonService(host="192.168.8.97")
    # emo_service.get_list()
    emo_service.play(10005)
