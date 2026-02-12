import requests
import json





class MapService():

    def __init__(self, host: str):
        self._base_url = f"http://{host}:50807"
        self._header = {
            "content-type": "application/json"
        }

    # def get_map_info(map_id: str):
    #     pass

    def get_stored_map_list(self):
        req_url = self._base_url + "/rpc/aimdk.protocol.MappingService/GetStoredMapNames"

    def get_map_topo_mags(self, map_id):
        req_url = self._base_url + "/rpc/aimdk.protocol.LocalizationService/GetTopoMsgs"
        request_json = {
            "map_id": map_id
        }
        resp = requests.post(req_url, json.dumps(request_json), headers=self._header)
        
        res_data = resp.json()['data']
        print(res_data)

    def get_current_working_map(self) -> str:
        req_url = self._base_url + "/rpc/aimdk.protocol.MappingService/GetCurrentWorkingMap"
        request_json = {
            "header":{},
            "command":"MappingCommand_GET_CURRENT_WORKING_MAP"
        }

        resp = requests.post(req_url, json.dumps(request_json), headers=self._header)
        
        # print(resp.json())
        res_data = resp.json()['data']
        # print(res_data['map_id'])
        return res_data['map_id']

    

if __name__ == "__main__":
    map_service = MapService("192.168.2.50")
    current_map_id = map_service.get_current_working_map()
    print("##current_map_id: ", current_map_id)
    map_service.get_map_topo_mags(current_map_id)
