
import os
import requests
import hashlib
from pathlib import Path
# import json
# import base64
# import wave
# import tempfile
import re
# from playsound3 import playsound
from dotenv import load_dotenv
import api.tts_hs as tts_hs
# import tts_hs as tts_hs
import api.tts_to_voice as tts_to_voice
from log.logger_config import logger
from pydub import AudioSegment
from pydub.playback import play

import time


load_dotenv()

class RobotVoiceCtl():
    def __init__(self):
        self._cache_enbale = True
        self._cache_base_path = os.environ['VoicePath']
        self._is_robot = os.environ['Robot'] == "True"
        self._voice_play_mode = os.environ['VoicePlayMode']
        self._tts_voice_service = tts_to_voice.TtsVoice(os.environ['OrinHost'])

        orin_host = os.environ['OrinHost']
        self._interaction_url = f"http://{orin_host}:59201"
        self._robot_audio_req_url = f"{self._interaction_url}/rpc/aimdk.protocol.InteractionTaskService/StartSpeceialInteractionTask"
        self._session = requests.Session()
        self._session.headers.update({'Content-Type': 'application/json'})

    def hash_text(self, text: str) -> str:
        md5 = hashlib.md5()
        md5.update(text.encode('utf-8'))
        return md5.hexdigest()

    # InteractionStatus
    #   InteractionStatus_Ready = 0;  // 复位, 打断当前播报
    #   InteractionStatus_Talk  = 1;  // 对话
    #   InteractionStatus_Task  = 2;  // 任务
    # def set_interaction_status(self, interaction_status: str):
    #     req_url = f"{self._interaction_url}/rpc/aimdk.protocol.InteractionStatusService/SetStatus"
    #     post_data = {
    #         "status": interaction_status
    #     }
    #     res = self._session.post(req_url,json=post_data)
    #     print("set_interaction_status=>res: ", res.text)
    
    # def get_interaction_status(self) -> str:
    #     req_url = f"{self._interaction_url}/rpc/aimdk.protocol.InteractionStatusService/GetStatus"
    #     res = self._session.post(req_url,json={})
    #     print("get_interaction_status=>res: ", res.json())
    #     status = res.json()['status']
    #     return status

    # def get_interaction_task_status(self, task_id) -> str:
    #     req_url = f"{self._interaction_url}/rpc/aimdk.protocol.InteractionTaskService/GetInteractionTaskStatus"
    #     req_data = {
    #         'task_id': task_id
    #     }
    #     res = self._session.post(req_url,json=req_data)
    #     print("get_interaction_task_status=>res: ", res.json())
    #     status = res.json()['status']
    #     return status


    # def check_speak_is_finish(self, task_id = 0) -> bool:
    #     while True:
    #         time.sleep(1)
    #         status = self.get_interaction_task_status(task_id)
    #         if status == "InteractionTaskStatus_Finished":
    #             return True
    #     return False

    def check_text_cache(self, text: str)->str:
        text_hash = self.hash_text(text)
        print("text_hash: ", text_hash)
        # file_path = self._cache_base_path + text_hash
        file_path = f"{self._cache_base_path}{text_hash}.wav"
        if os.path.exists(file_path):
            print("文件存在")
            return file_path
            # with open(file_path, 'r', encoding='utf-8') as file:
            #     data = json.load(file)
            #     return data

        else:
            print("文件不存在")
            return None

    def gen_robot_audio_format(
        self,
        text: str,
        audio_data: str,
        mc_id: str = '',
        is_end: int = 1
    ):
        # format_data = {
        #     "audio_id": "",
        #     "base64_audio_data": encode_audio_data
        # }
        if self._cache_enbale:
            text_hash = self.hash_text(text)
            file_path = f"{self._cache_base_path}{text_hash}.wav"
            file_to_save = open(file_path, "wb")
            file_to_save.write(audio_data)
            # with open(self._cache_base_path + text_hash, 'w') as file:
            #     json.dump(format_data, file, ensure_ascii=False)

        return file_path
    # 同步
    def play_audio_with_text(self, text: str, sync: bool = True) -> bool:

        task_id = 0
        if self._voice_play_mode == "TextToVoice":
            task_id = self.play_on_robot_with_text(text, sync)
        else:
            file_path = self.check_text_cache(text)
            if not file_path:
                tts_cli = tts_hs.TtsHs()
                audio_data = tts_cli.text_to_voice(text)
                file_path = self.gen_robot_audio_format(text, audio_data)
                print(f"file_path: {file_path}")

            self.play_audio(file_path)

        # if self._is_robot:
        #     self.check_speak_is_finish(task_id)

        return True

    def play_on_computer(self, file_path: str)->any:
        audio = AudioSegment.from_wav(file_path)
        play(audio)

    # def play_on_computer(self, format_audio_data):
        # audio_data = base64.b64decode(format_audio_data['base64_audio_data'])
        # temp_file = tempfile.NamedTemporaryFile(delete=False)
        # temp_file_path = temp_file.name
        # temp_file.write(audio_data)
        # temp_file.close()
        # playsound(temp_file_path)
        # os.remove(temp_file_path)

    def play_on_robot(self, file_path: str) ->any:
        # self.set_interaction_status("InteractionStatus_Ready")
        filename = Path(file_path).stem
        headers = {"content-type": "application/json"}
        data ={
            "audio_name" : filename,
            "motion_name": "",
            "emotion_name": ""
        }
        print("self._robot_audio_req_url:", self._robot_audio_req_url)
        print("data:", data)
        response = requests.post(
            self._robot_audio_req_url,
            headers=headers,
            json=data
        )

        print(response.text)
        return response

    def play_on_robot_with_text(self, text: str, sync: bool = True) -> any:
        # self.set_interaction_status("InteractionStatus_Ready")
        task_id = None
        if sync:
            # sentences = text.split('。')
            sentences = re.findall(r'[^。！？]*[。！？]', text)
            # sentences = re.split(r'[^。！？]*[。！？]', text)
            logger.info(f"sentences: {sentences}")
            for t in sentences:
                task_id = self._tts_voice_service.text_to_voice_sync(t)
                # time.sleep(0.5)
        else:
            task_id = self._tts_voice_service.text_to_voice(text)
        return task_id



    def play_audio(self, format_audio_data):
        # start_time = time.time()
        if self._is_robot:
            self.play_on_robot(format_audio_data)
        else:
            self.play_on_computer(format_audio_data)
        # print("time use: ",  time.time() - start_time)
        # print("play end ...")

    def interrupt_play_audio(self):
        self._tts_voice_service.stop_all_tts()
        # self.set_interaction_status("InteractionStatus_Talk")


if __name__ == "__main__":
    text = '作为服务国家双碳战略的排头兵，南方电网不仅构建着世界一流新型电力系统，更在数字新基建领域率先布局！我们创新打造的零碳智算中心，正以绿色基因重构算力格局,通过融入全国一体化算力网，实现清洁能源与数据要素的时空优化配置，让每一瓦西部绿电都转化为东部智算动能'
    robot_voice_service = RobotVoiceCtl()
    robot_voice_service.play_audio_with_text(text)
    # robot_voice_service.set_interaction_status("InteractionStatus_Ready")
    # robot_voice_service.get_interaction_status()