#!/usr/bin/env python3
"""ROS 2 broker between web_mapping and FAST-LIO2."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import signal
import shutil
import subprocess
import struct
import time
from collections import deque
from typing import Any, Optional

import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry, Path as RosPath
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Imu, PointCloud2, PointField
from std_msgs.msg import String

from web_fast_lio_broker.clean_map_postprocess import (
    ACCUMULATED_MAP_SUFFIX,
    GLOBAL_OPTIMIZED_MAP_SUFFIX,
    LEGACY_BACKEND_MAP_SUFFIX,
    LEGACY_FRONTEND_MAP_SUFFIX,
    CleanMapConfig,
    clean_map_config_for_preset,
    copy_accumulated_map_compat,
    read_pcd_xyzi,
    run_clean_map,
)

POSTPROCESS_METADATA_FILENAME = "postprocess.json"


@dataclass
class Session:
    name: str
    directory: Path
    map_path: Path
    accumulated_map_path: Path
    global_optimized_map_path: Path
    legacy_frontend_map_path: Path


class WebFastLioBroker(Node):
    def __init__(self) -> None:
        super().__init__("web_fast_lio_broker")
        self._declare_parameters()

        self.command_topic = self._str_param("mapping_command_topic")
        self.status_topic = self._str_param("mapping_status_topic")
        self.lidar_status_topic = self._str_param("lidar_status_topic")
        self.map_history_root = Path(self._str_param("map_history_root")).expanduser().resolve()
        self.default_session_name = self._str_param("default_session_name")
        self.manage_livox_driver = self._bool_param("manage_livox_driver")
        self.livox_launch_command = self._str_param("livox_launch_command")
        self.livox_config_path = self._str_param("livox_config_path")
        self.stop_livox_after_stop = self._bool_param("stop_livox_after_stop")
        self.stop_livox_after_save = self._bool_param("stop_livox_after_save")
        self.fast_lio_launch_command = self._str_param("fast_lio_launch_command")
        self.fast_lio_config_path = self._str_param("fast_lio_config_path")
        self.fast_lio_config_file = self._str_param("fast_lio_config_file")
        self.fast_lio_map_save_service = self._str_param("fast_lio_map_save_service")
        self.stop_fast_lio_after_stop = self._bool_param("stop_fast_lio_after_stop")
        self.stop_fast_lio_after_save = self._bool_param("stop_fast_lio_after_save")
        self.lidar_check_timeout_sec = self._float_param("lidar_check_timeout_sec")
        self.lidar_min_points = self._int_param("lidar_min_points")

        self.raw_livox_topic = self._str_param("raw_livox_topic")
        self.raw_observation_topic = self._str_param("raw_observation_topic")
        self.fast_lio_current_frame_topic = self._str_param("fast_lio_current_frame_topic")
        self.fast_lio_current_body_frame_topic = self._str_param("fast_lio_current_body_frame_topic")
        self.fast_lio_map_topic = self._str_param("fast_lio_map_topic")
        self.fast_lio_odom_topic = self._str_param("fast_lio_odom_topic")
        self.fast_lio_path_topic = self._str_param("fast_lio_path_topic")
        self.fast_lio_imu_topic = self._str_param("fast_lio_imu_topic")
        self.publish_fast_lio_current_frame = self._bool_param("publish_fast_lio_current_frame")
        self.clean_map = CleanMapConfig(
            enabled=self._bool_param("clean_map_enabled"),
            voxel_size=self._float_param("clean_map_voxel_size"),
            min_neighbors=self._int_param("clean_map_min_neighbors"),
            radius=self._float_param("clean_map_radius"),
            min_z=self._float_param("clean_map_min_z"),
            max_z=self._float_param("clean_map_max_z"),
            min_retention_ratio=self._float_param("clean_map_min_retention_ratio"),
            min_output_points=self._int_param("clean_map_min_output_points"),
            preset="default",
        )

        self.web_current_frame_topic = self._str_param("web_current_frame_topic")
        self.web_map_topic = self._str_param("web_map_topic")
        self.web_pose_topic = self._str_param("web_pose_topic")
        self.web_raw_path_topic = self._str_param("web_raw_path_topic")
        self.web_optimized_path_topic = self._str_param("web_optimized_path_topic")
        self.web_imu_topic = self._str_param("web_imu_topic")

        self._state = "idle"
        self._message = "等待开始建图"
        self._session: Optional[Session] = None
        self._last_command = ""
        self._last_result = ""
        self._livox_process: Optional[subprocess.Popen[str]] = None
        self._livox_process_match = ""
        self._fast_lio_process: Optional[subprocess.Popen[str]] = None
        self._last_odom: Optional[Odometry] = None
        self._last_path: Optional[RosPath] = None
        self._current_frame_frames = 0
        self._postprocess_last_result: dict[str, Any] = {}
        self._map_frames = 0
        self._raw_frames = 0
        self._raw_last_monotonic = 0.0
        self._raw_last_points = 0
        self._raw_last_stamp = 0.0
        self._raw_times: deque[float] = deque(maxlen=60)
        self._imu_frames = 0
        self._imu_last_monotonic = 0.0
        self._imu_last_stamp = 0.0
        self._imu_times: deque[float] = deque(maxlen=120)
        self._lidar_state = "disconnected"
        self._lidar_valid = False
        self._lidar_message = "雷达未连接"
        self._lidar_last_check: dict[str, Any] = {}
        self._lidar_check_deadline = 0.0
        self._lidar_check_started_at = 0.0
        self._lidar_closed = False

        reliable_qos = QoSProfile(depth=10)
        status_qos = QoSProfile(depth=1)
        status_qos.reliability = ReliabilityPolicy.RELIABLE
        status_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
        sensor_qos = QoSProfile(depth=50)
        sensor_qos.reliability = ReliabilityPolicy.BEST_EFFORT
        cloud_qos = QoSProfile(depth=5)
        cloud_qos.reliability = ReliabilityPolicy.BEST_EFFORT
        fast_lio_map_qos = QoSProfile(depth=1)
        fast_lio_map_qos.reliability = ReliabilityPolicy.RELIABLE
        web_map_qos = QoSProfile(depth=1)
        web_map_qos.reliability = ReliabilityPolicy.RELIABLE
        web_map_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL

        self.status_pub = self.create_publisher(String, self.status_topic, status_qos)
        self.lidar_status_pub = self.create_publisher(String, self.lidar_status_topic, status_qos)
        self.current_frame_pub = (
            self.create_publisher(PointCloud2, self.web_current_frame_topic, cloud_qos)
            if self.publish_fast_lio_current_frame
            else None
        )
        self.accumulated_map_pub = self.create_publisher(PointCloud2, self.web_current_frame_topic, web_map_qos)
        self.map_pub = self.create_publisher(PointCloud2, self.web_map_topic, web_map_qos)
        self.pose_pub = self.create_publisher(PoseStamped, self.web_pose_topic, reliable_qos)
        self.raw_path_pub = self.create_publisher(RosPath, self.web_raw_path_topic, reliable_qos)
        self.optimized_path_pub = self.create_publisher(RosPath, self.web_optimized_path_topic, reliable_qos)

        self.create_subscription(String, self.command_topic, self._command_callback, reliable_qos)
        self.create_subscription(PointCloud2, self.fast_lio_current_frame_topic, self._current_frame_callback, cloud_qos)
        self.create_subscription(PointCloud2, self.fast_lio_current_body_frame_topic, self._body_frame_callback, cloud_qos)
        self.create_subscription(PointCloud2, self.fast_lio_map_topic, self._map_callback, fast_lio_map_qos)
        self.create_subscription(Odometry, self.fast_lio_odom_topic, self._odom_callback, reliable_qos)
        self.create_subscription(RosPath, self.fast_lio_path_topic, self._path_callback, reliable_qos)
        self.create_subscription(Imu, self.web_imu_topic, self._imu_callback, sensor_qos)
        self.create_subscription(String, self.raw_observation_topic, self._raw_observation_callback, reliable_qos)

        self.create_timer(1.0, self._status_timer)
        self.map_history_root.mkdir(parents=True, exist_ok=True)
        self._publish_status()

    def _declare_parameters(self) -> None:
        self.declare_parameter("mapping_command_topic", "/web_mapping/command")
        self.declare_parameter("mapping_status_topic", "/web_mapping/status")
        self.declare_parameter("lidar_status_topic", "/web_mapping/lidar_status")
        self.declare_parameter("map_history_root", "maps")
        self.declare_parameter("default_session_name", "mid360_map")
        self.declare_parameter("manage_livox_driver", True)
        self.declare_parameter("livox_launch_command", "")
        self.declare_parameter("livox_config_path", "")
        self.declare_parameter("stop_livox_after_stop", True)
        self.declare_parameter("stop_livox_after_save", False)
        self.declare_parameter("fast_lio_launch_command", "")
        self.declare_parameter("fast_lio_config_path", "")
        self.declare_parameter("fast_lio_config_file", "mid360_fast_lio.yaml")
        self.declare_parameter("fast_lio_map_save_service", "/web_fast_lio/map_save")
        self.declare_parameter("stop_fast_lio_after_stop", True)
        self.declare_parameter("stop_fast_lio_after_save", False)
        self.declare_parameter("lidar_check_timeout_sec", 8.0)
        self.declare_parameter("lidar_min_points", 1)

        self.declare_parameter("raw_livox_topic", "/livox/lidar")
        self.declare_parameter("raw_observation_topic", "/web_mapping/raw_observation")
        self.declare_parameter("fast_lio_current_frame_topic", "/web_fast_lio/cloud_registered")
        self.declare_parameter("fast_lio_current_body_frame_topic", "/web_fast_lio/cloud_registered_body")
        self.declare_parameter("fast_lio_map_topic", "/web_fast_lio/laser_map")
        self.declare_parameter("fast_lio_odom_topic", "/web_fast_lio/odometry")
        self.declare_parameter("fast_lio_path_topic", "/web_fast_lio/path")
        self.declare_parameter("fast_lio_imu_topic", "/livox/imu")
        self.declare_parameter("publish_fast_lio_current_frame", False)
        self.declare_parameter("clean_map_enabled", True)
        self.declare_parameter("clean_map_voxel_size", 0.05)
        self.declare_parameter("clean_map_min_neighbors", 1)
        self.declare_parameter("clean_map_radius", 0.20)
        self.declare_parameter("clean_map_min_z", float("-inf"))
        self.declare_parameter("clean_map_max_z", float("inf"))
        self.declare_parameter("clean_map_min_retention_ratio", 0.05)
        self.declare_parameter("clean_map_min_output_points", 20000)

        self.declare_parameter("web_current_frame_topic", "/web_mapping/current_frame")
        self.declare_parameter("web_map_topic", "/web_mapping/global_map")
        self.declare_parameter("web_pose_topic", "/web_mapping/pose")
        self.declare_parameter("web_raw_path_topic", "/web_mapping/raw_path")
        self.declare_parameter("web_optimized_path_topic", "/web_mapping/optimized_path")
        self.declare_parameter("web_imu_topic", "/web_mapping/imu")

    def _str_param(self, name: str) -> str:
        return str(self.get_parameter(name).value or "")

    def _bool_param(self, name: str) -> bool:
        return bool(self.get_parameter(name).value)

    def _float_param(self, name: str) -> float:
        return float(self.get_parameter(name).value)

    def _int_param(self, name: str) -> int:
        return int(self.get_parameter(name).value)

    def _command_callback(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self._set_error("收到无效建图指令 JSON")
            return
        command = str(payload.get("command", "")).strip()
        self._last_command = command
        if command == "start_lidar":
            self._handle_start_lidar()
        elif command == "stop_lidar":
            self._handle_stop_lidar()
        elif command == "check_lidar":
            self._handle_check_lidar()
        elif command == "start":
            self._handle_start(payload)
        elif command == "stop":
            self._handle_stop()
        elif command == "save":
            self._handle_save()
        elif command == "rerun_postprocess":
            self._handle_rerun_postprocess(payload)
        elif command == "reset_error":
            self._state = "idle"
            self._message = "异常已清除"
            self._last_result = "reset"
            self._publish_status()
        else:
            self._set_error(f"未知建图指令: {command}")

    def _handle_start(self, payload: dict[str, Any]) -> None:
        if self._state in {"starting", "mapping", "saving", "stopping"}:
            self._last_result = "ignored"
            self._message = "建图已经在运行"
            self._publish_status()
            return
        check = self._check_lidar_health(update_state=True)
        if not check["valid"]:
            self._last_result = "rejected"
            self._message = f"雷达数据未就绪：{check['message']}"
            self._publish_lidar_status()
            self._publish_status()
            return
        self._state = "starting"
        self._message = "正在启动 FAST-LIO2"
        self._publish_status()

        session_name = self._safe_session_name(str(payload.get("session_name", "")).strip())
        self._session = self._make_session(session_name)
        self._last_odom = None
        self._last_path = None
        self._current_frame_frames = 0
        self._postprocess_last_result = {}
        self._map_frames = 0
        if not self._start_fast_lio_process():
            self._set_error("FAST-LIO2 启动失败")
            return

        self._state = "mapping"
        self._message = "FAST-LIO2 建图中"
        self._last_result = "started"
        self._publish_status()

    def _handle_start_lidar(self) -> None:
        if self._state in {"mapping", "saving", "stopping"}:
            self._last_result = "rejected"
            self._message = "建图运行中，不能单独启动雷达"
            self._publish_status()
            return
        self._lidar_closed = False
        if self._lidar_state == "starting":
            self._last_result = "starting_lidar"
            self._message = "雷达正在启动"
            self._publish_lidar_status()
            self._publish_status()
            return
        check = self._check_lidar_health(update_state=False)
        if check["valid"]:
            self._lidar_state = "online"
            self._lidar_valid = True
            self._lidar_message = "雷达数据有效"
            self._last_result = "lidar_already_online"
            self._message = self._lidar_message
            self._publish_lidar_status()
            self._publish_status()
            return
        self._lidar_state = "starting"
        self._lidar_valid = False
        self._lidar_check_deadline = 0.0
        self._lidar_check_started_at = 0.0
        self._lidar_message = "正在启动 Livox MID-360 驱动"
        self._last_result = "starting_lidar"
        self._publish_lidar_status()
        if not self._start_livox_process():
            self._lidar_state = "disconnected"
            self._lidar_message = "Livox MID-360 驱动启动失败"
            self._last_result = "lidar_start_failed"
            self._publish_lidar_status()
            self._publish_status()
            return
        self._begin_lidar_check()
        self._lidar_message = "已请求启动雷达，正在等待点云和 IMU 数据"
        self._last_result = "lidar_start_requested"
        self._message = self._lidar_message
        self._publish_lidar_status()
        self._publish_status()

    def _handle_stop_lidar(self) -> None:
        if self._state in {"starting", "mapping", "saving", "stopping"}:
            self._last_result = "rejected"
            self._message = "建图运行中，不能关闭雷达"
            self._publish_status()
            return
        if not self._livox_process_running():
            check = self._check_lidar_health(update_state=False)
            if check["valid"]:
                self._lidar_state = "online"
                self._lidar_valid = False
                self._lidar_check_deadline = 0.0
                self._lidar_check_started_at = 0.0
                self._lidar_message = "雷达由外部进程提供，未关闭"
                self._last_result = "lidar_external_running"
                self._message = self._lidar_message
                self._publish_lidar_status()
                self._publish_status()
                return
        self._lidar_state = "stopping"
        self._lidar_valid = False
        self._lidar_check_deadline = 0.0
        self._lidar_check_started_at = 0.0
        self._lidar_message = "正在关闭雷达"
        self._last_result = "stopping_lidar"
        self._publish_lidar_status()
        self._stop_livox_process()
        self._mark_lidar_closed("雷达已关闭")
        self._last_result = "lidar_stopped"
        self._message = self._lidar_message
        self._publish_lidar_status()
        self._publish_status()

    def _handle_check_lidar(self) -> None:
        if self._lidar_state == "checking":
            self._last_result = "checking_lidar"
            self._update_lidar_check()
            self._publish_lidar_status()
            self._publish_status()
            return
        self._begin_lidar_check()
        self._last_result = "checking_lidar"
        self._message = self._lidar_message
        self._update_lidar_check()
        self._publish_lidar_status()
        self._publish_status()

    def _begin_lidar_check(self) -> None:
        timeout = max(0.5, self.lidar_check_timeout_sec)
        now = time.monotonic()
        self._lidar_check_started_at = now
        self._lidar_check_deadline = now + timeout
        self._lidar_state = "checking"
        self._lidar_valid = False
        self._lidar_message = f"正在检测雷达，最长等待 {timeout:.1f} 秒"

    def _handle_stop(self) -> None:
        if self._state not in {"starting", "mapping", "saving"}:
            self._last_result = "ignored"
            self._message = "当前没有正在运行的建图"
            self._publish_status()
            return
        self._state = "stopping"
        self._message = "正在停止建图并保存当前地图"
        self._publish_status()
        saved = self._save_current_session(run_postprocess=False)
        if self.stop_fast_lio_after_stop or self.stop_livox_after_stop:
            self._message = "正在关闭雷达和 FAST-LIO2，随后运行后处理"
            self._publish_status()
        if self.stop_fast_lio_after_stop:
            self._stop_fast_lio_process()
        if self.stop_livox_after_stop:
            self._stop_livox_process()
            self._mark_lidar_closed("雷达已关闭，正在运行后处理" if saved else "雷达已关闭")
            self._publish_lidar_status()
        if saved:
            self._run_clean_map_postprocess()
        self._state = "stopped"
        postprocess_state = self._postprocess_last_result.get("state")
        if saved and postprocess_state == "completed":
            self._message = "已停止建图，里程计地图和后处理地图已保存"
        elif saved and postprocess_state == "failed":
            self._message = "已停止建图，里程计地图已保存，但后处理地图生成失败"
        elif saved:
            self._message = "已停止建图，可在地图库中查看保存结果"
        else:
            self._message = "已停止建图，但尚未生成可保存地图"
        self._last_result = "stopped_saved" if saved else "stopped_without_map"
        self._publish_status()

    def _handle_save(self) -> None:
        if self._session is None:
            self._last_result = "rejected"
            self._message = "没有可保存的建图会话"
            self._publish_status()
            return
        self._state = "saving"
        self._message = "正在保存地图"
        self._publish_status()
        ok = self._save_current_session()
        if self.stop_fast_lio_after_save:
            self._stop_fast_lio_process()
        if self.stop_livox_after_save:
            self._stop_livox_process()
            self._mark_lidar_closed("雷达已关闭")
            self._publish_lidar_status()
        self._state = "stopped" if ok else "error"
        self._message = "地图已保存" if ok else "地图保存失败"
        self._last_result = "saved" if ok else "save_failed"
        self._publish_status()

    def _handle_rerun_postprocess(self, payload: dict[str, Any]) -> None:
        if self._state in {"starting", "mapping", "saving", "stopping"}:
            self._last_result = "rejected"
            self._message = "建图运行中，不能重跑后处理"
            self._publish_status()
            return
        session_id = self._safe_session_name(str(payload.get("session_id", "")).strip())
        preset = str(payload.get("preset", "")).strip()
        session = self._session_from_history(session_id)
        if session is None:
            self._last_result = "postprocess_failed"
            self._postprocess_last_result = {
                "enabled": True,
                "state": "failed",
                "message": f"未找到可后处理的地图: {session_id or '-'}",
                "algorithm": "clean_map_v1",
            }
            self._message = self._postprocess_last_result["message"]
            self._publish_status()
            return
        previous_session = self._session
        previous_state = self._state
        self._session = session
        self._state = "saving"
        self._last_result = "postprocess_running"
        try:
            self._run_clean_map_postprocess(preset=preset)
        finally:
            self._session = previous_session
            self._state = previous_state if previous_state not in {"starting", "mapping", "saving", "stopping"} else "stopped"
        postprocess_state = self._postprocess_last_result.get("state")
        if postprocess_state == "completed":
            self._message = f"后处理已重跑: {session.name}"
            self._last_result = "postprocess_completed"
        else:
            self._message = f"后处理重跑失败: {self._postprocess_last_result.get('message', session.name)}"
            self._last_result = "postprocess_failed"
        self._publish_status()

    def _start_livox_process(self) -> bool:
        if not self.manage_livox_driver:
            return True
        if self._livox_process and self._livox_process.poll() is None:
            return True
        command = self._command_with_livox_config()
        if not command:
            return True
        self._message = "正在启动 Livox MID-360 驱动"
        self._publish_status()
        self.get_logger().info(f"Starting Livox MID-360 driver: {' '.join(command)}")
        try:
            self._livox_process = subprocess.Popen(command, text=True, start_new_session=True)
            self._livox_process_match = self._process_match(command)
        except OSError as exc:
            self.get_logger().error(f"Failed to start Livox MID-360 driver: {exc}")
            return False
        return True

    def _start_fast_lio_process(self) -> bool:
        if self._fast_lio_process and self._fast_lio_process.poll() is None:
            return True
        command = self._command_with_session_map_path()
        if not command:
            return True
        self.get_logger().info(f"Starting FAST-LIO2: {' '.join(command)}")
        try:
            self._fast_lio_process = subprocess.Popen(command, text=True, start_new_session=True)
        except OSError as exc:
            self.get_logger().error(f"Failed to start FAST-LIO2: {exc}")
            return False
        return True

    def _stop_livox_process(self) -> None:
        self._livox_process = self._stop_process(self._livox_process)
        self._stop_livox_residual_processes()

    def _stop_fast_lio_process(self) -> None:
        self._fast_lio_process = self._stop_process(self._fast_lio_process)

    def _mark_lidar_closed(self, message: str) -> None:
        self._raw_frames = 0
        self._raw_last_monotonic = 0.0
        self._raw_last_points = 0
        self._raw_last_stamp = 0.0
        self._raw_times.clear()
        self._imu_frames = 0
        self._imu_last_monotonic = 0.0
        self._imu_last_stamp = 0.0
        self._imu_times.clear()
        self._lidar_closed = True
        self._lidar_state = "disconnected"
        self._lidar_valid = False
        self._lidar_check_deadline = 0.0
        self._lidar_check_started_at = 0.0
        self._lidar_message = message
        self._lidar_last_check = {}

    def _stop_process(self, process: Optional[subprocess.Popen[str]]) -> Optional[subprocess.Popen[str]]:
        if process is None or process.poll() is not None:
            return None
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return None
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                return None
            process.wait(timeout=2.0)
        return None

    def _stop_livox_residual_processes(self) -> None:
        if not self._livox_process_match:
            return
        for pid in self._matching_livox_process_ids():
            self._terminate_pid_group(pid)

    def _matching_livox_process_ids(self) -> list[int]:
        try:
            result = subprocess.run(
                ["pgrep", "-af", "livox_ros_driver2_node"],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            return []
        pids: list[int] = []
        for line in result.stdout.splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            command = parts[1]
            if pid == os.getpid() or self._livox_process_match not in command:
                continue
            pids.append(pid)
        return pids

    def _terminate_pid_group(self, pid: int) -> None:
        try:
            pgid = os.getpgid(pid)
        except ProcessLookupError:
            return
        for sig, timeout in ((signal.SIGTERM, 2.0), (signal.SIGKILL, 1.0)):
            try:
                os.killpg(pgid, sig)
            except ProcessLookupError:
                return
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    return
                time.sleep(0.05)

    @staticmethod
    def _process_match(command: list[str]) -> str:
        if not command:
            return ""
        try:
            config_index = command.index("user_config_path:=")
        except ValueError:
            config_index = -1
        if config_index >= 0 and config_index + 1 < len(command):
            return command[config_index + 1]
        return " ".join(command[-4:])

    def _command_with_livox_config(self) -> list[str]:
        command = _split_command(self.livox_launch_command)
        if not command and self.livox_config_path:
            command = [
                "ros2",
                "run",
                "livox_ros_driver2",
                "livox_ros_driver2_node",
                "--ros-args",
                "-r",
                "__node:=livox_lidar_publisher",
                "-p",
                "xfer_format:=1",
                "-p",
                "multi_topic:=0",
                "-p",
                "data_src:=0",
                "-p",
                "publish_freq:=10.0",
                "-p",
                "output_data_type:=0",
                "-p",
                "frame_id:=livox_frame",
                "-p",
                "lvx_file_path:=/tmp/livox_test.lvx",
                "-p",
                f"user_config_path:={self.livox_config_path}",
                "-p",
                "cmdline_input_bd_code:=livox0000000001",
            ]
        return command

    def _command_with_session_map_path(self) -> list[str]:
        command = _split_command(self.fast_lio_launch_command)
        if not command and self.fast_lio_config_path:
            command = [
                "ros2",
                "launch",
                "fast_lio",
                "mapping.launch.py",
                f"config_path:={self.fast_lio_config_path}",
                f"config_file:={self.fast_lio_config_file}",
                "rviz:=false",
                f"cloud_registered_topic:={self.fast_lio_current_frame_topic}",
                f"cloud_registered_body_topic:={self.fast_lio_current_body_frame_topic}",
                f"laser_map_topic:={self.fast_lio_map_topic}",
                f"odometry_topic:={self.fast_lio_odom_topic}",
                f"path_topic:={self.fast_lio_path_topic}",
                f"map_save_service:={self.fast_lio_map_save_service}",
                "map_file_path:={map_file_path}",
            ]
        if not command or self._session is None:
            return command
        return [part.replace("{map_file_path}", str(self._session.map_path)) for part in command]

    def _save_current_session(self, *, run_postprocess: bool = True) -> bool:
        if self._session is None:
            return False
        self._session.directory.mkdir(parents=True, exist_ok=True)
        if self._map_frames <= 0 and self._last_odom is None and self._last_path is None:
            self.get_logger().warning("Map save skipped: FAST-LIO2 has not produced map or pose data yet.")
            return False
        fast_lio_running = self._fast_lio_process is not None and self._fast_lio_process.poll() is None
        service_ok = self._call_map_save() if fast_lio_running else self._session.map_path.is_file()
        self._write_pose_files()
        if self._session.map_path.is_file():
            try:
                copy_accumulated_map_compat(
                    self._session.map_path,
                    self._session.accumulated_map_path,
                    self._session.legacy_frontend_map_path,
                )
            except OSError as exc:
                self.get_logger().warning(f"Failed to copy accumulated map aliases: {exc}")
        if run_postprocess:
            self._run_clean_map_postprocess()
        return service_ok and self._session.map_path.is_file()

    def _call_map_save(self) -> bool:
        command = [
            "ros2",
            "service",
            "call",
            self.fast_lio_map_save_service,
            "std_srvs/srv/Trigger",
            "{}",
        ]
        try:
            result = subprocess.run(command, check=False, text=True, capture_output=True, timeout=30.0)
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.get_logger().warning(f"Failed to call FAST-LIO2 map_save service: {exc}")
            return False
        if result.returncode != 0:
            stderr = result.stderr.strip()
            self.get_logger().warning(f"FAST-LIO2 map_save service failed: {stderr}")
            return False
        output = result.stdout.strip()
        if "success=True" in output or "success: true" in output:
            return True
        self.get_logger().warning(f"FAST-LIO2 map_save did not report success: {output}")
        return False

    def _odom_callback(self, msg: Odometry) -> None:
        self._last_odom = msg
        pose = PoseStamped()
        pose.header = msg.header
        pose.pose = msg.pose.pose
        self.pose_pub.publish(pose)

    def _path_callback(self, msg: RosPath) -> None:
        self._last_path = msg
        self.raw_path_pub.publish(msg)
        self.optimized_path_pub.publish(msg)

    def _current_frame_callback(self, msg: PointCloud2) -> None:
        self._current_frame_frames += 1
        if self.current_frame_pub is not None:
            self.current_frame_pub.publish(msg)

    def _body_frame_callback(self, msg: PointCloud2) -> None:
        return

    def _map_callback(self, msg: PointCloud2) -> None:
        self._map_frames += 1
        if self.current_frame_pub is None:
            self.accumulated_map_pub.publish(msg)

    def _raw_observation_callback(self, msg: String) -> None:
        if self._lidar_closed:
            return
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        now = time.monotonic()
        self._raw_frames += 1
        self._raw_last_monotonic = now
        self._record_rate_sample(self._raw_times, now)
        self._raw_last_points = int(payload.get("point_count", 0) or 0)
        self._raw_last_stamp = float(payload.get("stamp_sec", 0.0) or 0.0)

    def _imu_callback(self, msg: Imu) -> None:
        if self._lidar_closed:
            return
        self._imu_frames += 1
        now = time.monotonic()
        self._imu_last_monotonic = now
        self._record_rate_sample(self._imu_times, now)
        self._imu_last_stamp = _stamp_to_float(msg.header.stamp)

    def _write_pose_files(self) -> None:
        if self._session is None:
            return
        poses = self._last_path.poses if self._last_path is not None else []
        if not poses and self._last_odom is not None:
            pose = PoseStamped()
            pose.header = self._last_odom.header
            pose.pose = self._last_odom.pose.pose
            poses = [pose]
        if not poses:
            return
        tum_path = self._session.directory / "poses_tum.txt"
        kitti_path = self._session.directory / "poses_kitti.txt"
        matrix_path = self._session.directory / "poses_matrix.txt"
        with tum_path.open("w", encoding="utf-8") as tum, kitti_path.open("w", encoding="utf-8") as kitti, matrix_path.open("w", encoding="utf-8") as matrix:
            for pose in poses:
                p = pose.pose.position
                q = pose.pose.orientation
                stamp = _stamp_to_float(pose.header.stamp)
                rot = _quat_to_rot(q.x, q.y, q.z, q.w)
                tum.write(f"{stamp:.9f} {p.x:.9f} {p.y:.9f} {p.z:.9f} {q.x:.9f} {q.y:.9f} {q.z:.9f} {q.w:.9f}\n")
                row = [
                    rot[0][0], rot[0][1], rot[0][2], p.x,
                    rot[1][0], rot[1][1], rot[1][2], p.y,
                    rot[2][0], rot[2][1], rot[2][2], p.z,
                ]
                kitti.write(" ".join(f"{value:.9f}" for value in row) + "\n")
                matrix.write(" ".join(f"{value:.9f}" for value in row) + "\n")

    def _run_clean_map_postprocess(self, *, preset: str = "") -> None:
        if self._session is None:
            return
        config = clean_map_config_for_preset(self.clean_map, preset)
        if not config.enabled:
            self._postprocess_last_result = {
                "enabled": False,
                "state": "disabled",
                "message": "CleanMap post-processing disabled",
            }
            return
        self._message = "正在运行 CleanMap v1 后处理，生成后处理地图"
        self._publish_status()
        started_at = time.time()
        started_monotonic = time.monotonic()
        result = run_clean_map(
            input_map_path=self._session.accumulated_map_path,
            output_map_path=self._session.global_optimized_map_path,
            config=config,
        )
        duration_sec = time.monotonic() - started_monotonic
        self._postprocess_last_result = {
            "enabled": True,
            "state": "completed" if result.success else "failed",
            "message": result.message,
            "input_points": result.input_points,
            "output_points": result.output_points,
            "retention_ratio": round(result.retention_ratio, 6),
            "duration_sec": round(duration_sec, 3),
            "started_at": round(started_at, 3),
            "completed_at": round(time.time(), 3),
            "output_map_path": str(self._session.global_optimized_map_path),
            "algorithm": "clean_map_v1",
            "preset": config.preset,
            "config": config.to_dict(),
        }
        self._write_postprocess_metadata()
        if result.success:
            self._publish_clean_map(result.output_map_path or self._session.global_optimized_map_path)
            self.get_logger().info(result.message)
        else:
            self.get_logger().warning(result.message)
        if self._lidar_closed:
            self._lidar_message = "雷达已关闭"

    def _write_postprocess_metadata(self) -> None:
        if self._session is None or not self._postprocess_last_result:
            return
        path = self._session.directory / POSTPROCESS_METADATA_FILENAME
        payload = {
            **self._postprocess_last_result,
            "input_map_path": str(self._session.accumulated_map_path),
            "output_map_path": str(self._session.global_optimized_map_path),
        }
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            self.get_logger().warning(f"Failed to write postprocess metadata: {exc}")

    def _publish_clean_map(self, map_path: Path) -> None:
        try:
            points = read_pcd_xyzi(map_path)
        except (OSError, ValueError, struct.error) as exc:
            self.get_logger().warning(f"Failed to publish post-processed map: {exc}")
            return
        if not points:
            return
        msg = PointCloud2()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"
        msg.height = 1
        msg.width = len(points)
        msg.fields = [
            _point_field("x", 0),
            _point_field("y", 4),
            _point_field("z", 8),
            _point_field("intensity", 12),
        ]
        msg.is_bigendian = False
        msg.point_step = 16
        msg.row_step = msg.point_step * msg.width
        msg.is_dense = True
        data = bytearray(msg.row_step)
        for index, point in enumerate(points):
            struct.pack_into(
                "<ffff",
                data,
                index * msg.point_step,
                point.x,
                point.y,
                point.z,
                point.intensity,
            )
        msg.data = bytes(data)
        self.map_pub.publish(msg)

    def _make_session(self, requested_name: str) -> Session:
        base = requested_name or f"{self.default_session_name}_{time.strftime('%Y%m%d_%H%M%S')}"
        session_dir = self.map_history_root / base
        suffix = 1
        while session_dir.exists() and any(session_dir.iterdir()):
            suffix += 1
            session_dir = self.map_history_root / f"{base}_{suffix}"
        name = session_dir.name
        session_dir.mkdir(parents=True, exist_ok=True)
        return Session(
            name=name,
            directory=session_dir,
            map_path=session_dir / f"{name}{LEGACY_BACKEND_MAP_SUFFIX}",
            accumulated_map_path=session_dir / f"{name}{ACCUMULATED_MAP_SUFFIX}",
            global_optimized_map_path=session_dir / f"{name}{GLOBAL_OPTIMIZED_MAP_SUFFIX}",
            legacy_frontend_map_path=session_dir / f"{name}{LEGACY_FRONTEND_MAP_SUFFIX}",
        )

    def _session_from_history(self, session_id: str) -> Optional[Session]:
        if not session_id:
            return None
        session_dir = (self.map_history_root / session_id).resolve()
        try:
            session_dir.relative_to(self.map_history_root)
        except ValueError:
            return None
        if not session_dir.is_dir():
            return None
        accumulated = session_dir / f"{session_id}{ACCUMULATED_MAP_SUFFIX}"
        if not accumulated.is_file():
            backend = session_dir / f"{session_id}{LEGACY_BACKEND_MAP_SUFFIX}"
            if backend.is_file():
                try:
                    shutil.copy2(backend, accumulated)
                except OSError as exc:
                    self.get_logger().warning(f"Failed to restore accumulated map alias: {exc}")
        if not accumulated.is_file():
            return None
        return Session(
            name=session_id,
            directory=session_dir,
            map_path=session_dir / f"{session_id}{LEGACY_BACKEND_MAP_SUFFIX}",
            accumulated_map_path=accumulated,
            global_optimized_map_path=session_dir / f"{session_id}{GLOBAL_OPTIMIZED_MAP_SUFFIX}",
            legacy_frontend_map_path=session_dir / f"{session_id}{LEGACY_FRONTEND_MAP_SUFFIX}",
        )

    @staticmethod
    def _safe_session_name(name: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in name.strip())
        return cleaned.strip("_")[:80]

    def _status_timer(self) -> None:
        if self._livox_process and self._livox_process.poll() is not None and self._state in {"starting", "mapping", "saving"}:
            self._set_error("Livox MID-360 驱动进程已退出")
            return
        if self._livox_process and self._livox_process.poll() is not None:
            self._livox_process = None
            if self._lidar_state in {"starting", "checking", "waiting"}:
                self._lidar_state = "disconnected"
                self._lidar_valid = False
                self._lidar_check_deadline = 0.0
                self._lidar_check_started_at = 0.0
                self._lidar_message = "Livox MID-360 驱动进程已退出"
                self._last_result = "lidar_process_exited"
                self._message = self._lidar_message
        if self._fast_lio_process and self._fast_lio_process.poll() is not None and self._state in {"starting", "mapping", "saving"}:
            self._set_error("FAST-LIO2 进程已退出")
            return
        self._update_lidar_check()
        self._publish_lidar_status()
        self._publish_status()

    def _publish_lidar_status(self) -> None:
        check = self._check_lidar_health(update_state=False)
        self._refresh_observed_lidar_state(check)
        self._lidar_last_check = {
            key: round(value, 3) if isinstance(value, float) else value
            for key, value in check.items()
        }
        age = check["raw_age_sec"]
        imu_age = check["imu_age_sec"]
        payload = {
            "text": self._lidar_message,
            "topic": self.raw_livox_topic,
            "state": self._lidar_state,
            "valid": self._lidar_valid,
            "checking": self._lidar_state == "checking",
            "frames": self._raw_frames,
            "hz": round(_rate_hz(self._raw_times), 2),
            "age_sec": None if age is None else round(age, 3),
            "last_points": self._raw_last_points,
            "last_stamp_sec": self._raw_last_stamp,
            "imu_topic": self.fast_lio_imu_topic,
            "web_imu_topic": self.web_imu_topic,
            "imu_frames": self._imu_frames,
            "imu_hz": round(_rate_hz(self._imu_times), 2),
            "imu_age_sec": None if imu_age is None else round(imu_age, 3),
            "imu_last_stamp_sec": self._imu_last_stamp,
            "check_timeout_sec": round(max(0.5, self.lidar_check_timeout_sec), 3),
            "check_remaining_sec": self._lidar_check_remaining_sec(),
            "min_points": max(1, self.lidar_min_points),
            "check": self._lidar_last_check,
        }
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        self.lidar_status_pub.publish(msg)

    def _publish_status(self) -> None:
        payload = {
            "type": "mapping_status",
            "state": self._state,
            "message": self._message,
            "session_name": self._session.name if self._session else "",
            "save_directory": str(self._session.directory) if self._session else "",
            "map_history_root": str(self.map_history_root),
            "last_command": self._last_command,
            "last_result": self._last_result,
            "lidar_state": self._lidar_state,
            "lidar_valid": self._lidar_valid,
            "lidar_message": self._lidar_message,
            "lidar_check": self._lidar_last_check,
            "lidar_checking": self._lidar_state == "checking",
            "postprocess": dict(self._postprocess_last_result),
        }
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        self.status_pub.publish(msg)

    def _set_error(self, message: str) -> None:
        self._state = "error"
        self._message = message
        self._last_result = "error"
        self._publish_status()

    def _check_lidar_health(self, update_state: bool) -> dict[str, Any]:
        now = time.monotonic()
        raw_age = now - self._raw_last_monotonic if self._raw_last_monotonic else None
        imu_age = now - self._imu_last_monotonic if self._imu_last_monotonic else None
        raw_topic = self.raw_livox_topic
        raw_topic_publishers = self.count_publishers(raw_topic) if raw_topic else 0
        imu_topic_publishers = self.count_publishers(self.fast_lio_imu_topic) if self.fast_lio_imu_topic else 0
        raw_topic_exists = raw_topic_publishers > 0
        imu_topic_exists = imu_topic_publishers > 0
        raw_recent = raw_age is not None and raw_age < 2.0
        imu_recent = imu_age is not None and imu_age < 2.0
        min_points = max(1, self.lidar_min_points)
        has_points = self._raw_last_points >= min_points
        valid = raw_topic_exists and raw_recent and has_points and imu_topic_exists and imu_recent
        if valid:
            state = "online"
            message = "雷达数据有效"
        elif not raw_topic_exists:
            state = "disconnected"
            message = f"未发现雷达话题 {raw_topic or '-'}"
        elif not raw_recent:
            state = "waiting"
            message = "已发现雷达话题，等待点云数据"
        elif not has_points:
            state = "invalid"
            message = f"雷达点云点数不足，当前 {self._raw_last_points} 点，至少需要 {min_points} 点"
        elif not imu_topic_exists:
            state = "invalid"
            message = f"未发现 IMU 话题 {self.fast_lio_imu_topic or '-'}"
        elif not imu_recent:
            state = "waiting"
            message = "已发现 IMU 话题，等待 IMU 数据"
        else:
            state = "invalid"
            message = "雷达数据无效"
        result = {
            "valid": valid,
            "state": state,
            "message": message,
            "raw_topic": raw_topic,
            "raw_topic_exists": raw_topic_exists,
            "raw_topic_publishers": raw_topic_publishers,
            "raw_age_sec": raw_age,
            "raw_frames": self._raw_frames,
            "raw_last_points": self._raw_last_points,
            "raw_hz": _rate_hz(self._raw_times),
            "min_points": min_points,
            "imu_topic": self.fast_lio_imu_topic,
            "web_imu_topic": self.web_imu_topic,
            "imu_topic_exists": imu_topic_exists,
            "imu_topic_publishers": imu_topic_publishers,
            "imu_age_sec": imu_age,
            "imu_frames": self._imu_frames,
            "imu_hz": _rate_hz(self._imu_times),
        }
        if update_state:
            self._lidar_state = state
            self._lidar_valid = valid
            self._lidar_message = message
            self._lidar_last_check = {
                key: round(value, 3) if isinstance(value, float) else value
                for key, value in result.items()
            }
        elif self._lidar_state == "online" and not valid:
            self._lidar_state = state
            self._lidar_valid = False
            self._lidar_message = message
        return result

    def _refresh_observed_lidar_state(self, check: dict[str, Any]) -> None:
        if self._lidar_state in {"checking", "starting", "stopping"}:
            return
        if self._lidar_closed:
            self._lidar_state = "disconnected"
            self._lidar_valid = False
            if not self._lidar_message:
                self._lidar_message = "雷达已关闭"
            if self._state == "idle":
                self._message = self._lidar_message
            return
        if check["valid"]:
            self._lidar_closed = False
        if self._lidar_valid:
            if check["valid"]:
                self._lidar_state = "online"
                self._lidar_message = "雷达数据有效"
                if self._state == "idle":
                    self._message = self._lidar_message
                return
            self._lidar_valid = False
        if check["valid"]:
            self._lidar_state = "online"
            self._lidar_valid = True
            self._lidar_message = "雷达数据有效"
            if self._state == "idle":
                self._message = self._lidar_message
            return
        self._lidar_valid = False
        self._lidar_state = check["state"]
        self._lidar_message = check["message"]
        if self._state == "idle":
            self._message = self._lidar_message

    def _livox_process_running(self) -> bool:
        return self._livox_process is not None and self._livox_process.poll() is None

    def _update_lidar_check(self) -> None:
        if self._lidar_state != "checking":
            return
        check = self._check_lidar_health(update_state=False)
        now = time.monotonic()
        self._lidar_last_check = {
            key: round(value, 3) if isinstance(value, float) else value
            for key, value in check.items()
        }
        if check["valid"]:
            self._lidar_check_deadline = 0.0
            self._lidar_check_started_at = 0.0
            self._lidar_state = "online"
            self._lidar_valid = True
            self._lidar_message = check["message"]
            self._last_result = "lidar_valid"
            self._message = check["message"]
            return
        if self._lidar_check_deadline and now >= self._lidar_check_deadline:
            if self._livox_process_running():
                self._stop_livox_process()
            self._lidar_check_deadline = 0.0
            self._lidar_check_started_at = 0.0
            self._lidar_state = "timeout"
            self._lidar_valid = False
            self._lidar_message = f"雷达检测超时：{check['message']}"
            self._last_result = "lidar_timeout"
            self._message = self._lidar_message
            return
        remaining = max(0.0, self._lidar_check_deadline - now)
        self._lidar_message = f"{check['message']}，继续等待 {remaining:.1f} 秒"
        self._message = self._lidar_message

    def _lidar_check_remaining_sec(self) -> Optional[float]:
        if self._lidar_state != "checking" or not self._lidar_check_deadline:
            return None
        return round(max(0.0, self._lidar_check_deadline - time.monotonic()), 3)

    @staticmethod
    def _record_rate_sample(samples: deque[float], now: float) -> None:
        if samples and now - samples[-1] > 2.0:
            samples.clear()
        samples.append(now)


def _split_command(command: str) -> list[str]:
    return [part for part in command.split() if part]


def _stamp_to_float(stamp: Any) -> float:
    return float(stamp.sec) + float(stamp.nanosec) * 1e-9


def _point_field(name: str, offset: int) -> PointField:
    field = PointField()
    field.name = name
    field.offset = offset
    field.datatype = PointField.FLOAT32
    field.count = 1
    return field


def _rate_hz(samples: deque[float]) -> float:
    if len(samples) < 2:
        return 0.0
    elapsed = samples[-1] - samples[0]
    if elapsed <= 0:
        return 0.0
    return (len(samples) - 1) / elapsed


def _quat_to_rot(x: float, y: float, z: float, w: float) -> list[list[float]]:
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm <= 0:
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]


def main() -> None:
    rclpy.init()
    node = WebFastLioBroker()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node._stop_livox_process()
        node._stop_fast_lio_process()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
