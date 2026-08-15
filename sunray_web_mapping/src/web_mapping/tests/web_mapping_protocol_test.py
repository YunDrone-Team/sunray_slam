#!/usr/bin/env python3
"""Protocol checks for the web mapping demo.

This test is intentionally independent from ROS 2 imports, so it can run in a
plain Python environment and still verify the browser/bridge binary contract.
"""

from __future__ import annotations

import json
import struct
from array import array
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "web_mapping"))

from web_mapping.protocol import (  # noqa: E402
    DEFAULT_MAP_HISTORY_ROOT,
    DEFAULT_SOURCES,
    SOURCE_LABELS,
    VALID_MAPPING_COMMANDS,
    VALID_MAPPING_STATES,
    VALID_SOURCES,
    WEB_MAPPING_TOPICS,
)
from web_mapping.runtime.mapping_manager import MappingBackend, MappingBackendResult, MappingManager  # noqa: E402


def make_binary_cloud_payload(header: dict, values: array) -> bytes:
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    padding = (4 - ((8 + len(header_bytes)) % 4)) % 4
    data_offset = 8 + len(header_bytes) + padding
    return (
        struct.pack("<II", len(header_bytes), data_offset)
        + header_bytes
        + (b"\x00" * padding)
        + values.tobytes()
    )


def decode_like_frontend(payload: bytes) -> tuple[dict, array]:
    header_length = struct.unpack_from("<I", payload, 0)[0]
    data_offset = struct.unpack_from("<I", payload, 4)[0]
    header = json.loads(payload[8 : 8 + header_length].decode("utf-8"))
    assert data_offset % 4 == 0
    values = array("f")
    values.frombytes(payload[data_offset:])
    return header, values


def test_binary_cloud_payload_contract() -> None:
    header = {
        "type": "cloud",
        "source": "optimized",
        "point_count": 2,
        "layout": "float32_xyzi",
        "stride": 4,
        "has_intensity": True,
    }
    values = array("f", [1.0, 2.0, 3.0, 0.4, 4.0, 5.0, 6.0, 0.8])
    payload = make_binary_cloud_payload(header, values)
    decoded_header, decoded_values = decode_like_frontend(payload)

    assert decoded_header == header
    assert list(decoded_values) == list(values)


def test_default_sources_include_raw_preview() -> None:
    assert set(DEFAULT_SOURCES) == VALID_SOURCES
    assert set(SOURCE_LABELS) == VALID_SOURCES


def test_mapping_control_state_machine_shell() -> None:
    manager = MappingManager()

    initial = manager.snapshot()
    assert initial["state"] == "idle"
    assert "start" not in initial["allowed_commands"]
    assert "start_lidar" in initial["allowed_commands"]
    assert "stop_lidar" in initial["allowed_commands"]
    assert "check_lidar" in initial["allowed_commands"]
    assert set(initial["states"]) == VALID_MAPPING_STATES

    rejected_start = manager.handle_command("start", {"session_name": "demo"})
    assert not rejected_start.accepted
    assert rejected_start.state == "idle"

    manager.apply_status({"lidar_state": "online", "lidar_valid": True, "lidar_message": "雷达数据有效"})
    assert "start" in manager.snapshot()["allowed_commands"]

    start_result = manager.handle_command("start", {"session_name": "demo"})
    assert start_result.accepted
    assert start_result.state == "mapping"
    assert "save" not in manager.snapshot()["allowed_commands"]

    save_while_mapping_result = manager.handle_command("save", {"save_directory": "/tmp/maps"})
    assert not save_while_mapping_result.accepted
    assert save_while_mapping_result.state == "mapping"

    stop_result = manager.handle_command("stop", {})
    assert stop_result.accepted
    assert stop_result.state == "stopped"
    assert "save" in manager.snapshot()["allowed_commands"]

    save_after_stop_result = manager.handle_command("save", {})
    assert save_after_stop_result.accepted
    assert save_after_stop_result.state == "stopped"


class AsyncMappingBackend(MappingBackend):
    available = True

    def start(self, request):
        return MappingBackendResult(True, "已请求开始建图", {"async": True})

    def stop(self, request):
        return MappingBackendResult(True, "已请求停止建图", {"async": True})


def test_async_mapping_commands_stay_in_transitional_states() -> None:
    manager = MappingManager(AsyncMappingBackend())
    manager.apply_status({"lidar_state": "online", "lidar_valid": True})

    start_result = manager.handle_command("start", {"session_name": "demo"})
    assert start_result.accepted
    assert start_result.state == "starting"
    assert manager.snapshot()["state"] == "starting"

    stop_result = manager.handle_command("stop", {})
    assert stop_result.accepted
    assert stop_result.state == "stopping"
    assert manager.snapshot()["state"] == "stopping"


def test_mapping_start_requires_completed_lidar_check() -> None:
    manager = MappingManager()

    manager.apply_status({"lidar_state": "checking", "lidar_valid": False, "lidar_checking": True})
    snapshot = manager.snapshot()
    assert snapshot["lidar_checking"] is True
    assert "start" not in snapshot["allowed_commands"]
    assert not manager.handle_command("start", {"session_name": "demo"}).accepted

    manager.apply_status({"lidar_state": "timeout", "lidar_valid": False, "lidar_checking": False})
    snapshot = manager.snapshot()
    assert snapshot["lidar_checking"] is False
    assert "start" not in snapshot["allowed_commands"]

    manager.apply_status({"lidar_state": "online", "lidar_valid": True, "lidar_checking": False})
    snapshot = manager.snapshot()
    assert "start" in snapshot["allowed_commands"]


def test_mapping_protocol_commands_are_explicit() -> None:
    assert VALID_MAPPING_COMMANDS == {
        "start_lidar",
        "stop_lidar",
        "check_lidar",
        "start",
        "stop",
        "save",
        "rerun_postprocess",
        "reset_error",
    }


def test_mapping_postprocess_rerun_is_history_only() -> None:
    manager = MappingManager()

    missing_session_result = manager.handle_command("rerun_postprocess", {})
    assert not missing_session_result.accepted

    result = manager.handle_command("rerun_postprocess", {"session_id": "session"})
    assert result.accepted
    assert result.state == "stopped"

    manager.apply_status({"state": "mapping", "lidar_state": "online", "lidar_valid": True})
    assert not manager.handle_command("rerun_postprocess", {"session_id": "session"}).accepted


def test_mapping_postprocess_rerun_accepts_preset() -> None:
    class CapturingBackend(MappingBackend):
        available = True

        def __init__(self) -> None:
            self.request = None

        def rerun_postprocess(self, request):
            self.request = request
            return MappingBackendResult(True, "ok")

    backend = CapturingBackend()
    manager = MappingManager(backend)

    result = manager.handle_command("rerun_postprocess", {"session_id": "session", "preset": "detail"})

    assert result.accepted
    assert backend.request is not None
    assert backend.request.preset == "detail"


def test_web_mapping_broker_contract_topics_are_stable() -> None:
    assert WEB_MAPPING_TOPICS == {
        "raw_cloud": "/web_mapping/raw_cloud",
        "current_frame": "/web_mapping/current_frame",
        "global_map": "/web_mapping/global_map",
        "pose": "/web_mapping/pose",
        "raw_path": "/web_mapping/raw_path",
        "optimized_path": "/web_mapping/optimized_path",
        "imu": "/web_mapping/imu",
        "raw_observation": "/web_mapping/raw_observation",
        "lidar_status": "/web_mapping/lidar_status",
        "mapping_command": "/web_mapping/command",
        "mapping_status": "/web_mapping/status",
    }
    assert DEFAULT_MAP_HISTORY_ROOT == "maps"


if __name__ == "__main__":
    test_binary_cloud_payload_contract()
    test_default_sources_include_raw_preview()
    test_mapping_control_state_machine_shell()
    test_async_mapping_commands_stay_in_transitional_states()
    test_mapping_start_requires_completed_lidar_check()
    test_mapping_protocol_commands_are_explicit()
    test_mapping_postprocess_rerun_is_history_only()
    test_mapping_postprocess_rerun_accepts_preset()
    test_web_mapping_broker_contract_topics_are_stable()
    print("web mapping protocol ok")
