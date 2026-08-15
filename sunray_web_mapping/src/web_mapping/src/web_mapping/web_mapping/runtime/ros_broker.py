"""ROS topic backend for algorithm-specific Web Mapping brokers."""

from __future__ import annotations

import json
import time
from typing import Any

from std_msgs.msg import String

from web_mapping.runtime.mapping_manager import MappingBackend, MappingBackendResult, MappingCommandRequest


class RosBrokerBackend(MappingBackend):
    name = "ros_broker"
    available = True

    def __init__(self, publisher: Any) -> None:
        self._publisher = publisher
        self._seq = 0

    def start(self, request: MappingCommandRequest) -> MappingBackendResult:
        return self._publish("start", request, "已请求开始建图")

    def start_lidar(self, request: MappingCommandRequest) -> MappingBackendResult:
        return self._publish("start_lidar", request, "已请求启动雷达")

    def stop_lidar(self, request: MappingCommandRequest) -> MappingBackendResult:
        return self._publish("stop_lidar", request, "已请求关闭雷达")

    def check_lidar(self, request: MappingCommandRequest) -> MappingBackendResult:
        return self._publish("check_lidar", request, "已请求检测雷达")

    def stop(self, request: MappingCommandRequest) -> MappingBackendResult:
        return self._publish("stop", request, "已请求停止建图")

    def save(self, request: MappingCommandRequest) -> MappingBackendResult:
        return self._publish("save", request, "已请求保存地图")

    def rerun_postprocess(self, request: MappingCommandRequest) -> MappingBackendResult:
        return self._publish("rerun_postprocess", request, "已请求重跑后处理")

    def _publish(self, command: str, request: MappingCommandRequest, message: str) -> MappingBackendResult:
        self._seq += 1
        payload = {
            "type": "mapping_command",
            "seq": self._seq,
            "command": command,
            "session_name": request.session_name,
            "session_id": request.session_id,
            "preset": request.preset,
            "save_directory": request.save_directory,
            "stamp": time.time(),
        }
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        self._publisher.publish(msg)
        return MappingBackendResult(True, message, {"seq": self._seq, "async": True})
