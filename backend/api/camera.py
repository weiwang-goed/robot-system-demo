import base64  # 引入 base64 模块
import time

import cv2
import numpy as np
import requests

import asyncio
import websockets
import json

from flask import Flask, request, jsonify
import threading
import random

app = Flask(__name__)

send_ae_enable = False
send_infrared_enable = False
play_video_enable = False
current_video_enable = False

@app.route('/ping')
def ping():
    return 'pong'

@app.route('/playstart')
def play_start():
    global play_video_enable
    play_video_enable = True
    return "ok"

@app.route('/playstop')
def play_stop():
    global play_video_enable
    play_video_enable = False
    return "ok"

@app.route('/aestart')
def ae_start():
    global send_ae_enable
    send_ae_enable = True
    return "ok"

@app.route('/aestop')
def aestop():
    global send_ae_enable
    send_ae_enable = False
    return "ok"


@app.route('/infstart')
def inf_start():
    global send_infrared_enable
    send_infrared_enable = True
    return "ok"

@app.route('/infstop')
def inf_stop():
    global send_infrared_enable
    send_infrared_enable = False
    return "ok"

class CameraService():
    def __init__(self, host: str):
        self._session = requests.Session()
        self._session.headers.update({'Content-Type': 'application/json'})
        self._base_url = f"http://{host}:56422"
        self._cam_req_url = f"{self._base_url}/rpc/aimdk.protocol.CameraSnapshotsService/GetCameraSnapshots"
        payload = {"names": ["xinying_chest_right"]}

    # position: xinying_chest_right or xinying_chest_left
    def get_camera_snapshots(self, position):

        try:
            payload = {"names": ["xinying_chest_left","xinying_chest_right"]}
            # payload = {"names": ["xinying_chest_right"]}
            print("Sending request to camera snapshot service...")
            # response = requests.post(url, json=payload, headers=headers, timeout=5)
            response = self._session.post(self._cam_req_url,json=payload)
            if response.status_code == 200:
                print("Successfully received response from the service.")
                return response.json()
            else:
                print(f"Error: Received status code {response.status_code}")
                print(f"Response content: {response.text}")
                return None
        except Exception as e:
            print(f"Exception occurred while making the request: {e}")
            return None


def display_image_from_snapshot(snapshot_data):
    if not snapshot_data or 'responses' not in snapshot_data:
        print("No snapshot data available or 'responses' key missing.")
        return
    # print("snapshot_data['responses']==>", snapshot_data['responses'])
    for camera_response in snapshot_data['responses']:
        print("Processing camera response...")
        # print("camera_response==>", camera_response)
        if 'images' not in camera_response:
            print("No 'images' key found in camera response.")
            continue
        print("camera_response['images']==>", camera_response['images'])
        for image in camera_response['images']:
            print(image)
            if image.get('result') == "SUCCESS" and image.get('data'):
                try:
                    print("Processing image data...")
                    # 使用 Base64 解码数据
                    image_data_base64 = image['data']
                    if not image_data_base64:
                        print("Image data is empty.")
                        continue

                    image_data = base64.b64decode(image_data_base64)
                    format_type = image.get('format')
                    img_type = image.get('type')
                    width = int(image.get('width', 0))
                    height = int(image.get('height', 0))

                    print(f"Image format: {format_type}, width: {width}, height: {height}")

                    if width <= 0 or height <= 0:
                        print("Invalid image dimensions.")
                        continue

                    if format_type == "bgr8":
                        # 处理 BGR 图像
                        expected_size = width * height * 3  # 每个像素 3 字节
                        actual_size = len(image_data)
                        if actual_size != expected_size:
                            print(f"Data size mismatch for bgr8 image: expected {expected_size}, but got {actual_size}")
                            continue

                        # 将二进制数据转换为 NumPy 数组并重塑为图像
                        img = np.frombuffer(image_data, dtype=np.uint8).reshape((height, width, 3))
                        print(f"Displaying {img_type} image...")
                        cv2.imshow(f"Camera Snapshot - {img_type}", img)
                        cv2.waitKey(1)  # Display the image for 1 millisecond

                    elif format_type == "mjpeg":
                        # 处理 MJPEG 图像
                        img = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
                        if img is None:
                            print("Failed to decode MJPEG image, resulting img is None.")
                        else:
                            print(f"Displaying {img_type} MJPEG image...")
                            cv2.imshow(f"Camera Snapshot - {img_type}", img)
                            cv2.waitKey(1)  # Display the image for 1 millisecond

                            # cv2.imwrite('saved_image.jpg', img)

                    elif format_type == "16UC1":
                        # 处理 16 位深度图像
                        expected_size = height * width * 2  # 每个像素 2 字节
                        actual_size = len(image_data)
                        if actual_size != expected_size:
                            print(
                                f"Data size mismatch for 16UC1 image: expected {expected_size}, but got {actual_size}")
                            continue

                        img = np.frombuffer(image_data, dtype=np.uint16).reshape((height, width))
                        print(f"Displaying depth image with shape: {img.shape}")
                        # 归一化深度图以便显示
                        img_normalized = cv2.normalize(img, None, 0, 65535, cv2.NORM_MINMAX)
                        img_normalized = (img_normalized / 256).astype('uint8')  # 转换为8位以便显示
                        cv2.imshow(f"Depth Image - {img_type}", img_normalized)
                        cv2.waitKey(1)

                    elif format_type == "tif":
                        # 处理 TIFF 图像
                        img = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_UNCHANGED)
                        if img is None:
                            print("Failed to decode TIFF image, resulting img is None.")
                        else:
                            print(f"Displaying {img_type} TIFF image...")
                            # 如果深度图像是 float32 类型，可能需要归一化以便显示
                            if img.dtype == np.float32 or img.dtype == np.float64:
                                img_display = cv2.normalize(img, None, 0, 1, cv2.NORM_MINMAX)
                                cv2.imshow(f"Depth Image - {img_type} (TIFF)", img_display)
                            else:
                                cv2.imshow(f"Camera Snapshot - {img_type} (TIFF)", img)
                            cv2.waitKey(1)  # Display the image for 1 millisecond

                    else:
                        print(f"Unsupported image format: {format_type}")

                except Exception as e:
                    print(f"Exception while processing image: {e}")
                    # 如需调试，可取消注释以下两行以打印完整的异常堆栈
                    # import traceback
                    # traceback.print_exc()
            else:
                result = image.get('result', 'Unknown')
                data_length = len(image['data']) if image.get('data') else 'None'
                print(f"Image not successful or no data: result={result}, data length={data_length}")




async def send_ae_value(ws):
    global send_ae_enable
    while True:
        if send_ae_enable:
            print(".......................")
            json_data = json.dumps({
                "type": "ae_value",
                "data": 18
            })
            await ws.send(json_data)
        time.sleep(3)


def filter_and_draw_lines(image_path, length_threshold=500, output_path=None):
    """
    读取图片，检测轮廓中的长线条，并根据方向绘制横线和竖线。
    
    :param image_path: 输入图片的路径
    :param length_threshold: 轮廓长度阈值（单位：像素），用于过滤短线条
    :param output_path: 保存结果图片的路径（可选）
    :return: 处理后的图像（NumPy 数组格式）
    """
    # 1. 读取图片
    image = image_path #cv2.imread(image_path)

    # 检查图片是否成功加载
    if image is None:
        raise FileNotFoundError("Error: 图片文件未找到，请检查路径！")

    # 2. 转换为灰度图
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 3. 预处理：使用高斯模糊去噪
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # 4. 使用 Canny 边缘检测
    edges = cv2.Canny(blurred, threshold1=50, threshold2=150)

    # 5. 查找轮廓
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 创建一个副本用于绘制符合条件的轮廓
    filtered_contour_image = image.copy()

    # 6. 过滤并绘制长线条
    for contour in contours:
        # 计算当前轮廓的长度
        length = cv2.arcLength(contour, closed=False)
        
        # 如果长度大于设定的阈值，则进一步处理
        if length > length_threshold:
            # 拟合直线
            [vx, vy, x0, y0] = cv2.fitLine(contour, cv2.DIST_L2, 0, 0.01, 0.01)
            
            # 判断方向：通过比较 vx 和 vy 的绝对值大小
            if abs(vx) > abs(vy):  # 横线（x 方向分量较大）
                color = (0, 255, 0)  # 红色
            else:  # 竖线（y 方向分量较大）
                color = (0, 255, 0)  # 绿色
            
            # 绘制轮廓
            cv2.drawContours(filtered_contour_image, [contour], -1, color, 2)

    # 如果提供了输出路径，则保存结果
    # if output_path:
    #     cv2.imwrite(output_path, filtered_contour_image)

    return filtered_contour_image

def detect_faces(input_image_path, model_weights, output_image_path="AAA.jpg"):
    """
    使用 OpenCV 的 YuNet 模型进行人脸检测，并绘制检测结果。

    :param input_image_path: 输入图片路径
    :param model_weights: 预训练模型权重文件路径 (.onnx)
    :param output_image_path: 输出图片保存路径（默认为 "detected_faces.jpg"）
    :return: 检测到的人脸信息 (NumPy 数组) 和 带有标注的图像 (OpenCV 格式)
    """
    # ============================
    # Step 1: 加载预训练模型
    # ============================

    # 加载人脸检测模型
    face_detector = cv2.FaceDetectorYN_create(model_weights, "", (320, 320))

    # ============================
    # Step 2: 读取输入图像
    # ============================

    img = input_image_path # cv2.imread(input_image_path)

    if img is None:
        print("Error: 图片文件未找到，请检查路径！")
        return None, None

    # 获取图像尺寸并设置输入图像的尺寸
    height, width = img.shape[:2]
    face_detector.setInputSize((width, height))

    # ============================
    # Step 3: 进行人脸检测
    # ============================

    _, faces = face_detector.detect(img)

    # 如果没有检测到人脸
    if faces is None:
    #    print("未检测到人脸！")
        return img

    # 将检测结果转换为 NumPy 数组
    faces = np.array(faces)

    # ============================
    # Step 4: 绘制检测结果
    # ============================

    for face in faces:
        # 提取人脸框和关键点
        box = list(map(int, face[:4]))  # [x, y, w, h]
        confidence = face[4]            # 置信度
        keypoints = face[5:].reshape((5, 2))  # 5个关键点 (眼睛、鼻子、嘴角)

        # 绘制人脸框
        cv2.rectangle(img, (box[0], box[1]), (box[0] + box[2], box[1] + box[3]), (255, 0, 0), 2)
        cv2.putText(img, f"face : {confidence:.2f}", (box[0], box[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        # 绘制关键点
        for keypoint in keypoints:
            cv2.circle(img, (int(keypoint[0]), int(keypoint[1])), 2, (255, 0, 0), 2)

    # ============================
    # Step 5: 保存结果
    # ============================

    # 保存结果图像
    #cv2.imwrite(output_image_path, img)
    #print(f"检测结果已保存到 {output_image_path}")

    # 返回检测结果和带有标注的图像
    return img


def process_image(input_image, scale_percent=50, length_threshold=100, aspect_ratio_threshold=5):
    """
    处理输入图像，识别横线和竖线，并在原图上绘制结果。
    
    :param input_image: 输入的图像（NumPy 数组格式）
    :param scale_percent: 缩放比例（默认 50%，表示缩小到原始尺寸的一半）
    :param length_threshold: 轮廓长度阈值，用于过滤短线条（单位：像素）
    :param aspect_ratio_threshold: 宽高比阈值，用于区分横线和竖线
    :return: 处理后的图像（NumPy 数组格式）
    """
    # 检查输入是否有效
    if input_image is None:
        raise ValueError("输入图像无效，请检查路径或图像数据！")

    # 提取相机参数
    ppx = 810.820618
    ppy = 601.685547
    fx = 496.738037
    fy = 496.793213
    coeffs = [0.0344925858, -0.0261887442, 0.0220763143, -0.0168235097]

    # 构建相机内参矩阵 K 和畸变系数 D
    K = np.array([[fx, 0, ppx],
                  [0, fy, ppy],
                  [0, 0, 1]])
    D = np.array(coeffs)

    # 矫正图像
    map1, map2 = cv2.fisheye.initUndistortRectifyMap(K, D, np.eye(3), K, input_image.shape[:2][::-1], cv2.CV_32FC1)
    undistorted_image = cv2.remap(input_image, map1, map2, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

    # 转换为灰度图
    gray = cv2.cvtColor(undistorted_image, cv2.COLOR_BGR2GRAY)

    # 预处理：使用高斯模糊去噪
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # 使用 Canny 边缘检测
    edges = cv2.Canny(blurred, threshold1=50, threshold2=150)

    # 查找轮廓
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 过滤并绘制长线条（直接在矫正后的图像上绘制）
    for contour in contours:
        # 计算当前轮廓的长度
        length = cv2.arcLength(contour, closed=False)

        # 如果长度大于设定的阈值，则进一步判断方向
        if length > length_threshold:
            # 获取轮廓的边界框
            x, y, w, h = cv2.boundingRect(contour)

            # 计算宽高比
            aspect_ratio = w / float(h) if h != 0 else float('inf')

            # 判断是横线还是竖线
            if aspect_ratio > aspect_ratio_threshold:
                color = (0, 0, 255)  # 红色表示横线
            elif aspect_ratio < 1 / aspect_ratio_threshold:
                color = (0, 255, 0)  # 绿色表示竖线
            else:
                continue  # 不符合横线或竖线条件的轮廓跳过

            # 在原图上绘制轮廓
            cv2.drawContours(undistorted_image, [contour], -1, color, 5)

    # 缩放图像到指定尺寸
    width = int(undistorted_image.shape[1] * scale_percent / 100)
    height = int(undistorted_image.shape[0] * scale_percent / 100)
    dim = (width, height)
    resized_image = cv2.resize(undistorted_image, dim, interpolation=cv2.INTER_LINEAR)

    return resized_image


async def video_stream(websocket):
    # send_ae_thread = threading.Thread(target=send_ae_value, args=(websocket,))
    # send_ae_thread.start()
    global current_video_enable
    global play_video_enable
    global send_ae_enable
    global send_infrared_enable
    send_ae_count = 0
    send_infrared_count = 0

    # cam_service = CameraService("192.168.2.50")
    cam_service = CameraService("127.0.0.1")
    while True:

        if send_ae_enable:
            send_ae_count += 1
            if send_ae_count >= 1:
                send_ae_count = 0
                random_value = round(random.uniform(0.0, 15.0), 1)
                json_data = json.dumps({
                    "type": "ae_value",
                    "data": random_value
                })
                await websocket.send(json_data)

        if play_video_enable and (not current_video_enable):
            json_data = json.dumps({
                "type": "playstart",
                "data": 0
            })
            current_video_enable = True
            print("json_data: ", json_data)
            await websocket.send(json_data)
        
        if (not play_video_enable) and current_video_enable:
            json_data = json.dumps({
                "type": "playstop",
                "data": 0
            })
            current_video_enable = False
            await websocket.send(json_data)

        # if send_infrared_enable:
        #     send_infrared_count += 1
        #     if send_infrared_count > 5:
        #         send_infrared_count = 0
        #         random_value = round(random.uniform(26.0, 28.0), 1)
        #         json_data = json.dumps({
        #             "type": "infrared_value",
        #             "data": random_value
        #         })
        #         await websocket.send(json_data)



        print("Requesting new camera snapshot...")
        snapshot_data = cam_service.get_camera_snapshots("xinying_chest_left")
        if not snapshot_data or 'responses' not in snapshot_data:
            continue
        for camera_response in snapshot_data['responses']:
            print("camera_response name: ", camera_response["name"])
            if 'images' not in camera_response:
                print("No 'images' key found in camera response.")
                continue
            for image in camera_response['images']:
                # print(image)
                if image.get('result') == "SUCCESS" and image.get('data'):
                    image_data_base64 = image['data']
                    if not image_data_base64:
                        print("Image data is empty.")
                        continue

                    image_data = base64.b64decode(image_data_base64)
                    format_type = image.get('format')
                    img_type = image.get('type')
                    width = int(image.get('width', 0))
                    height = int(image.get('height', 0))

                    print(f"Image format: {format_type}, width: {width}, height: {height}")
                    if format_type == "mjpeg":
                        # 处理 MJPEG 图像
                        img = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
                        if img is None:
                            print("Failed to decode MJPEG image, resulting img is None.")
                        else:
                            print(f"Displaying {img_type} MJPEG image...")
                            # cv2.imshow(f"Camera Snapshot - {img_type}", img)
                            # cv2.waitKey(1)  # Display the image for 1 millisecond

                            if camera_response["name"] == "xinying_chest_left":
                                img = cv2.rotate(img, cv2.ROTATE_180)

                            img = filter_and_draw_lines(img, length_threshold=1000, output_path="")

                            img = detect_faces(img, "face_detection_yunet_2023mar.onnx")

                            # timestamp = time.time()
                            # # print(timestamp)  # 例如：1712345678.123456

                            # # 如果需要整数秒（去掉小数部分）
                            # timestamp_int = int(time.time()*1000)
                            # cv2.imwrite(f"./images/{timestamp_int}.jpg", img)

                            _, buffer = cv2.imencode('.jpg', img)
                            # 转换为 base64
                            jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                            
                            # 发送给客户端
                            # await websocket.send(jpg_as_text)
                            if camera_response["name"] == "xinying_chest_right":
                                json_data = json.dumps({
                                    "type": "chest_right_image",
                                    "data": jpg_as_text
                                })
                                await websocket.send(json_data)
                            elif camera_response["name"] == "xinying_chest_left":

                                json_data = json.dumps({
                                    "type": "chest_left_image",
                                    "data": jpg_as_text
                                })
                                await websocket.send(json_data)
                            # 控制帧率
                            await asyncio.sleep(0.3)



def start_flask():
    app.run(host='0.0.0.0', port=7005, use_reloader=False, debug=False)


async def main():
    # 启动 WebSocket 服务器
    async with websockets.serve(video_stream, "0.0.0.0", 8765):
        print("WebSocket 服务器已启动，监听端口 8765")
        await asyncio.Future()  # 永久运行

# 正确启动事件循环
if __name__ == "__main__":
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    print("Flask 服务器已启动，主线程可以继续运行其他任务...")
    asyncio.run(main())