#!/bin/bash
curl -i -X POST \
    'http://127.0.0.1:53176/rpc/aimdk.protocol.PncService/PlanningNaviToGoal' \
    -H 'Content-Type: application/json' \
    -H 'timeout: 60000' \
    -d '{
        "header": {
            "timestamp": {
                "seconds": 0,
                "nanos": 0,
                "ms_since_epoch": 0
            },
            "control_source": 0
        },
        "task_id": "196",
        "map_id": 1767068974292,
        "target_id": 14,
        "guide_line_id": 0,
        "ackerman_mode": false
}'

# curl -i     -H 'content-type:application/json' \
#             -H 'timeout: 1000' \
#             -X POST 'http://127.0.0.1:51011/rpc/aimdk.protocol.SystemService/GetSystemState' \
#             -d '{}'