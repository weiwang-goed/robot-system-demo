#!/usr/bin/env python3
"""
FaceID TCP 服务器
订阅 ROS2 FaceID 话题，通过 TCP 长连接将数据转发给远程客户端
"""

import socket
import struct
import threading
import json
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from ros2_plugin_proto.msg import RosMsgWrapper
from aimdk.protocol_pb2 import FaceIdResult
from google.protobuf.json_format import MessageToDict


class FaceIdSubscriber(Node):
    def __init__(self, server_instance):
        super().__init__("face_id_tcp_server")
        self.server = server_instance

        qos_profile = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )

        self.subscription = self.create_subscription(
            RosMsgWrapper,
            "/agent/vision/face_id/pb_3Aaimdk_2Eprotocol_2EFaceIdResult",
            self.face_id_callback,
            qos_profile,
        )

        self.get_logger().info("已开始订阅 FaceID 数据...")

    def face_id_callback(self, msg):
        try:
            if msg.serialization_type != "pb":
                self.get_logger().warn(
                    f"收到不支持的序列化类型: {msg.serialization_type}"
                )
                return

            # 拼接 bytes
            raw_bytes = b"".join(msg.data)

            # 解析 protobuf
            face_id_result = FaceIdResult()
            face_id_result.ParseFromString(raw_bytes)

            # 转换为 JSON 字符串
            json_str = json.dumps(
                MessageToDict(face_id_result, preserving_proto_field_name=True),
                ensure_ascii=False,
                indent=2
            )
            
            # 本地输出（与 get_face_id.py 格式一致）
            self.get_logger().info(f"FaceID 结果: {json_str}")
            print(f"FaceID 结果: {json_str}")

            # 将 JSON 字符串编码为 bytes 并转发给所有连接的客户端
            json_bytes = json_str.encode('utf-8')
            self.server.broadcast_data(json_bytes)

        except Exception as e:
            self.get_logger().error(f"解析 FaceID 数据时出现错误: {e}")


class FaceIdTCPServer:
    def __init__(self, host="0.0.0.0", port=8888):
        self.host = host
        self.port = port
        self.clients = []
        self.clients_lock = threading.Lock()
        self.socket = None
        self.running = False
        self.node = None

    def broadcast_data(self, data):
        """向所有连接的客户端广播数据"""
        if not data:
            return

        # 使用长度前缀协议：先发送4字节的长度（大端序），再发送数据
        data_length = len(data)
        header = struct.pack(">I", data_length)  # >I 表示大端序的4字节无符号整数
        message = header + data

        with self.clients_lock:
            disconnected_clients = []
            for client_socket, client_addr in self.clients:
                try:
                    client_socket.sendall(message)
                except (socket.error, OSError) as e:
                    print(f"发送数据到 {client_addr} 失败: {e}")
                    disconnected_clients.append((client_socket, client_addr))

            # 移除断开的客户端
            for client in disconnected_clients:
                self.clients.remove(client)
                try:
                    client[0].close()
                except:
                    pass
                print(f"客户端 {client[1]} 已断开连接")

    def handle_client(self, client_socket, client_addr):
        """处理单个客户端连接"""
        print(f"客户端 {client_addr} 已连接")
        try:
            # 保持连接，等待服务器发送数据
            while self.running:
                # 接收心跳或控制消息（可选）
                try:
                    client_socket.settimeout(1.0)
                    data = client_socket.recv(1024)
                    if not data:
                        break
                    # 可以在这里处理客户端发送的控制消息
                except socket.timeout:
                    continue
                except (socket.error, OSError):
                    break
        except Exception as e:
            print(f"处理客户端 {client_addr} 时出错: {e}")
        finally:
            with self.clients_lock:
                if (client_socket, client_addr) in self.clients:
                    self.clients.remove((client_socket, client_addr))
            try:
                client_socket.close()
            except:
                pass
            print(f"客户端 {client_addr} 已断开")

    def start(self):
        """启动服务器"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
        self.running = True

        print(f"FaceID TCP 服务器已启动，监听 {self.host}:{self.port}")

        # 初始化 ROS2 节点
        rclpy.init()
        self.node = FaceIdSubscriber(self)

        # 启动 ROS2 消息处理线程
        ros_thread = threading.Thread(target=self._ros_spin, daemon=True)
        ros_thread.start()

        try:
            while self.running:
                try:
                    client_socket, client_addr = self.socket.accept()
                    with self.clients_lock:
                        self.clients.append((client_socket, client_addr))

                    # 为每个客户端启动处理线程
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_addr),
                        daemon=True,
                    )
                    client_thread.start()
                except OSError:
                    if self.running:
                        raise
        except KeyboardInterrupt:
            print("\n正在关闭服务器...")
        finally:
            self.stop()

    def _ros_spin(self):
        """ROS2 消息处理循环"""
        try:
            # 使用 spin 持续处理消息（阻塞式，直到节点被移除）
            rclpy.spin(self.node)
        except Exception as e:
            print(f"ROS2 消息处理出错: {e}")

    def stop(self):
        """停止服务器"""
        self.running = False

        # 关闭所有客户端连接
        with self.clients_lock:
            for client_socket, client_addr in self.clients:
                try:
                    client_socket.close()
                except:
                    pass
            self.clients.clear()

        # 关闭服务器套接字
        if self.socket:
            try:
                self.socket.close()
            except:
                pass

        # 关闭 ROS2 节点
        if self.node:
            self.node.destroy_node()
            rclpy.shutdown()

        print("服务器已关闭")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="FaceID TCP 服务器")
    parser.add_argument(
        "--host", default="0.0.0.0", help="服务器监听地址（默认: 0.0.0.0）"
    )
    parser.add_argument(
        "--port", type=int, default=8888, help="服务器监听端口（默认: 8888）"
    )

    args = parser.parse_args()

    server = FaceIdTCPServer(host=args.host, port=args.port)
    try:
        server.start()
    except Exception as e:
        print(f"服务器启动失败: {e}")
        server.stop()


if __name__ == "__main__":
    main()
