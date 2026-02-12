import subprocess
import requests
import json


def set_agent_properties(mode_name):
    api_url = "http://127.0.0.1:59301/rpc/aimdk.protocol.AgentControlService/SetAgentPropertiesRequest"
    request_json = {
        "contents": { "properties": { "2": mode_name } }
    }
    resp = requests.post(api_url, json.dumps(request_json), headers={"content-type": "application/json"})
    print("resp: ", resp.json())
    return resp.json()

def aima_stop(module_name: str):
    return ["aima", "em", "stop-app", module_name]

def aima_start(module_name: str):
    return ["aima", "em", "start-app", module_name]

def restart_module(module_name: str):
    result = subprocess.run(aima_stop(module_name), capture_output=True, text=True)
    print("标准输出:", result.stdout)
    print("标准错误:", result.stderr)
    print("返回码:", result.returncode)
    result = subprocess.run(aima_start(module_name), capture_output=True, text=True)
    print("标准输出:", result.stdout)
    print("标准错误:", result.stderr)
    print("返回码:", result.returncode)

def set_voice_mode(mode_name: str):
    set_agent_properties(mode_name)
    restart_module('agent')


if __name__ == '__main__':
    # restart_module("agent")
    set_voice_mode("only_voice")
    # set_voice_mode("normal")