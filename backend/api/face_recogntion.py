import face_recognition
import numpy as np
import cv2
import json
import threading
import time
import requests
import base64
import random

class FaceRecogntionService():
    def __init__(
        self,
        config_file_path="../config/face-recogntion.json",
        img_source="videoCapture"
    ):
        self._base_url = "http://127.0.0.1"
        self._know_face_data = []
        self._known_face_encodings = []
        self._known_face_names = []
        self._img_source = img_source
        self._video_capture = None
        # if img_source == "videoCapture":
        #     self._video_capture = cv2.VideoCapture(0)
        self._config_file_path = self.load_know_face_data(config_file_path)
        self._current_face_ids = []
        self._first_record = {}

        # self._know_face_data_list = []

    
    @property
    def current_face_ids(self):
        return self._current_face_ids

    @property
    def know_face_data(self):
        return self._know_face_data

    def load_know_face_data(self, file_path: str):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self._know_face_data = data['know_face_data']
        know_face_img_path = data['know_face_img_path']
        know_face_data = []
        for face_data in data['know_face_data']:
            try:
                img_data = face_recognition.load_image_file(know_face_img_path + face_data['face_pic'])
                face_encoding = face_recognition.face_encodings(img_data)[0]
                # print("face_encoding", face_encoding)
                self._known_face_encodings.append(face_encoding)
                self._known_face_names.append({
                    "face_id": face_data["face_id"],
                    "name": face_data["name"]
                })
            except KeyError as e:
                print(f"数据加载失败: {face_data} - 错误: {str(e)}")

    def get_current_face_info(self):
        know_face_data = []
        face_ids = self._current_face_ids

        for face_id in face_ids:
            matches = [item for item in self._know_face_data if item.get("face_id") == face_id]
            if matches:
                know_face_data.append(matches[0])
        return know_face_data

    def check_face_record(self, face_id) -> bool:
        current_timestamp = int(time.time())
        if face_id in self._first_record.keys():
            timestamp = self._first_record[face_id]
            if current_timestamp - timestamp > 3600:
                self._first_record[face_id] = current_timestamp
                return True
            else:
                return False

        self._first_record[face_id] = current_timestamp
        return True
    
    def voice_logic(self):
        know_face_data = self.get_current_face_info()
        print("know_face_data: ", know_face_data)
        if len(know_face_data) > 0:
            face_info = know_face_data[0]
            if not self.check_face_record(face_info['face_id']):
                return
            response_text = random.choice(face_info['response'])
            requests.post(self._base_url + ":8002/robot/speak", json.dumps({
                "text": response_text
            }), headers={"content-type": "application/json"})

        # requests.post("http://192.168.2.50:8002", json.dumps(script_info), headers={"content-type": "application/json"})


    def run(self):
        face_locations = []
        face_encodings = []
        face_names = []
        process_this_frame = True

        session = requests.Session()
        response = session.get(self._base_url + ":5002/video_stream", stream=True, headers={'Accept': 'text/event-stream'})


        try:
            for line in response.iter_lines():
                if line:
                    # 解析SSE事件
                    if line.startswith(b'data: '):
                        # 获取JPEG图像数据
                        # print("line[:]: ", line[:100])
                        jpeg_data = line[6:]  # 去掉 'data: ' 前缀

                        jpeg_data = json.loads(jpeg_data.decode('utf-8'))
                        if 'type' not in jpeg_data or jpeg_data['type'] != 'frame':
                            continue
                        # print("jpeg_data: ", jpeg_data)
                        # frame_base64 = jpeg_data['data']
                        # print("frame_base64: ", frame_base64)
                        # 将字节数据转换为numpy数组
                        frame_base64 = jpeg_data['data']
                        # print("jpeg_data: ", jpeg_data)
                        image_data = base64.b64decode(frame_base64)
                        nparr = np.frombuffer(image_data, np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        # print("frame: ", frame)
                        if frame is None:
                            continue
                            
                        if process_this_frame:
                            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                            face_locations = face_recognition.face_locations(rgb_small_frame)
                            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
                            face_names = []
                            self._current_face_ids = []

                            for face_encoding in face_encodings:
                                # 检查是否与已知人脸匹配
                                matches = face_recognition.compare_faces(self._known_face_encodings, face_encoding)
                                name = "Unknown"
                                face_distances = face_recognition.face_distance(self._known_face_encodings, face_encoding)

                                if len(face_distances) > 0:
                                    best_match_index = np.argmin(face_distances)
                                    if matches[best_match_index]:
                                        name = self._known_face_names[best_match_index]['face_id']

                                face_names.append(name)
                                self._current_face_ids.append(name)

                            if len(self._current_face_ids) > 0:
                                self.voice_logic()

                        process_this_frame = not process_this_frame

                        # # 绘制人脸框和标签
                        # for (top, right, bottom, left), name in zip(face_locations, face_names):
                        #     top *= 4
                        #     right *= 4
                        #     bottom *= 4
                        #     left *= 4

                        #     cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
                        #     cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 0, 255), cv2.FILLED)
                        #     font = cv2.FONT_HERSHEY_DUPLEX
                        #     cv2.putText(frame, name, (left + 6, bottom - 6), font, 1.0, (255, 255, 255), 1)
                        
                        # # 显示结果
                        # cv2.imshow('Face Recognition - SSE', frame)
                        
                        # # 按'q'退出
                        # if cv2.waitKey(1) & 0xFF == ord('q'):
                        #     break
        except KeyboardInterrupt:
            print("程序被用户中断")
        finally:
            # cv2.destroyAllWindows()
            session.close()
        


if __name__ == '__main__':
    print("Main start ...")
    face_recogntion_service = FaceRecogntionService()
    # face_recogntion_service.run()
    def get_current_face_ids():
        while True:
            pass
            # time.sleep(1)
            # print("current_face_ids: ", face_recogntion_service.current_face_ids)

    
    thread = threading.Thread(target=get_current_face_ids)
    thread.start()
    face_recogntion_service.run()



