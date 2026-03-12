export PYTHONPATH="/agibot/agibot_a2_aimdk-dev1.3/prebuilt/ros2_plugin_proto_aarch64/local/lib/python3.10/dist-packages:$PYTHONPATH"
export PYTHONPATH="/agibot/agibot_a2_aimdk-dev1.3/protocol/protobuf:$PYTHONPATH"
export LD_LIBRARY_PATH="/agibot/agibot_a2_aimdk-dev1.3/prebuilt/ros2_plugin_proto_aarch64/lib:$LD_LIBRARY_PATH"

echo "请手动运行命令 aima em load-env"

source /agibot/agibot_a2_aimdk-dev1.3/prebuilt/ros2_plugin_proto_aarch64/share/ros2_plugin_proto/local_setup.bash
python3 server.py
