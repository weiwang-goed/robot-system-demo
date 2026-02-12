import socket
import struct
import sys
import json
import requests
import time

from face_to_user import faceMapping
 



def main():
    import argparse

    parser = argparse.ArgumentParser(description="FaceID TCP 客户端")
    parser.add_argument(
        "--host", default="localhost", help="服务器地址（默认: localhost）"
    )
    parser.add_argument(
        "--port", type=int, default=8888, help="服务器端口（默认: 8888）"
    )

    args = parser.parse_args()

    try:
        # 连接到服务器
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((args.host, args.port))
        print("已连接到FaceId 服务器")
        
        buffer = b""
        header_size = 4

        last_time = time.time()
        COOLDOWN_SECONDS = 5
        
        # 阻塞接收并显示所有数据
        while True:
            data = sock.recv(4096)
            if not data:
                break
            
            buffer += data
            
            # 处理完整消息
            while len(buffer) >= header_size:
                # 读取长度前缀（大端序）
                data_length = struct.unpack(">I", buffer[:header_size])[0]
                
                # 检查是否有完整消息
                total_size = header_size + data_length
                if len(buffer) < total_size:
                    break
                
                # 提取完整消息（JSON 数据）
                message_data = buffer[header_size:total_size]
                buffer = buffer[total_size:]
                
                # === 替换原打印逻辑：解析 JSON 并提取 face_id_result 内容 ===
                try:
                    json_str = message_data.decode('utf-8')
                    face_id_result = json.loads(json_str)
                    
                    face_ids = [face['face_id'] for face in face_id_result['faces']]
                    
                    
                    current_time = time.time()

                    # 冷却机制
                    if current_time - last_time > COOLDOWN_SECONDS:
                        try:
                            print(f"face_ids: {face_ids}")

                            map_file = "../data/face_id_person.json"
                            mapper = faceMapping(map_file)
                            
                            names = []

                            for i in face_ids:
                                names.append(mapper.get_user_id(i))
                                print(f"user_name: {names}")
                            
                            requests.post("http://localhost:7000/api/face_detected", params={"usernames": names})
                            
                            last_time = time.time()

                        except Exception as req_err:
                            print(f"后端请求失败{req_err}")
                    
                except (UnicodeDecodeError, json.JSONDecodeError) as e:
                    print(f"❌ JSON 解析失败: {e}", file=sys.stderr)
            
    except KeyboardInterrupt:
        print("\n退出中...", file=sys.stderr)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
    finally:
        try:
            sock.close()
        except:
            pass


if __name__ == "__main__":
    main()
