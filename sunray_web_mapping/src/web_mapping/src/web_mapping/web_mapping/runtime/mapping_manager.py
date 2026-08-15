"""Mapping control state machine for the browser bridge.

The default backend is intentionally a no-op shell. It keeps the WebSocket
contract stable while the real SLAM launch/service integration is added by the
host project.
"""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any, Optional

from web_mapping.protocol import VALID_MAPPING_COMMANDS, VALID_MAPPING_STATES


@dataclass(frozen=True)
class MappingCommandRequest:
    command: str
    session_name: str = ""
    save_directory: str = ""
    session_id: str = ""
    preset: str = ""


@dataclass(frozen=True)
class MappingBackendResult:
    accepted: bool
    message: str
    details: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class MappingCommandResult:
    command: str
    accepted: bool
    state: str
    message: str
    details: Optional[dict[str, Any]] = None


class MappingBackend:
    """Backend control hook to be replaced by the owning SLAM workspace."""

    name = "stub"
    available = False

    def start(self, request: MappingCommandRequest) -> MappingBackendResult:
        return MappingBackendResult(True, "已进入建图模式，实际启动功能待接入。")

    def stop(self, request: MappingCommandRequest) -> MappingBackendResult:
        return MappingBackendResult(True, "已停止建图，实际停止功能待接入。")

    def save(self, request: MappingCommandRequest) -> MappingBackendResult:
        return MappingBackendResult(True, "已请求保存地图，实际保存功能待接入。")

    def start_lidar(self, request: MappingCommandRequest) -> MappingBackendResult:
        return MappingBackendResult(True, "已请求启动雷达，实际启动功能待接入。")

    def stop_lidar(self, request: MappingCommandRequest) -> MappingBackendResult:
        return MappingBackendResult(True, "已请求关闭雷达，实际关闭功能待接入。")

    def check_lidar(self, request: MappingCommandRequest) -> MappingBackendResult:
        return MappingBackendResult(True, "已请求检测雷达，实际检测功能待接入。")

    def rerun_postprocess(self, request: MappingCommandRequest) -> MappingBackendResult:
        return MappingBackendResult(True, "已请求重跑后处理，实际后处理功能待接入。")


class MappingManager:
    """Small state machine used by the Web UI mapping controls."""

    def __init__(self, backend: Optional[MappingBackend] = None) -> None:
        self._backend = backend or MappingBackend()
        self._lock = threading.Lock()
        self._state = "idle"
        self._message = "等待开始"
        self._session_name = ""
        self._save_directory = ""
        self._last_command = ""
        self._last_result = ""
        self._lidar_state = "disconnected"
        self._lidar_valid = False
        self._lidar_message = "雷达未连接"
        self._lidar_check: dict[str, Any] = {}
        self._lidar_checking = False
        self._postprocess: dict[str, Any] = {}
        self._seq = 0
        self._updated_at = time.time()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self._state,
                "message": self._message,
                "session_name": self._session_name,
                "save_directory": self._save_directory,
                "last_command": self._last_command,
                "last_result": self._last_result,
                "lidar_state": self._lidar_state,
                "lidar_valid": self._lidar_valid,
                "lidar_message": self._lidar_message,
                "lidar_check": dict(self._lidar_check),
                "lidar_checking": self._lidar_checking,
                "postprocess": dict(self._postprocess),
                "command_seq": self._seq,
                "updated_at": self._updated_at,
                "backend": {
                    "name": self._backend.name,
                    "available": self._backend.available,
                },
                "allowed_commands": sorted(self._allowed_commands_unlocked()),
                "states": sorted(VALID_MAPPING_STATES),
            }

    def apply_status(self, payload: dict[str, Any]) -> None:
        with self._lock:
            state = str(payload.get("state", self._state)).strip() or self._state
            if state in VALID_MAPPING_STATES:
                self._state = state
            message = str(payload.get("message", "")).strip()
            if message:
                self._message = message
            session_name = str(payload.get("session_name", "")).strip()
            if session_name:
                self._session_name = session_name
            save_directory = str(payload.get("save_directory", "")).strip()
            if save_directory:
                self._save_directory = save_directory
            last_command = str(payload.get("last_command", "")).strip()
            if last_command:
                self._last_command = last_command
            last_result = str(payload.get("last_result", "")).strip()
            if last_result:
                self._last_result = last_result
            lidar_state = str(payload.get("lidar_state", "")).strip()
            if lidar_state:
                self._lidar_state = lidar_state
            if "lidar_valid" in payload:
                self._lidar_valid = bool(payload.get("lidar_valid"))
            if "lidar_checking" in payload:
                self._lidar_checking = bool(payload.get("lidar_checking"))
            lidar_message = str(payload.get("lidar_message", "")).strip()
            if lidar_message:
                self._lidar_message = lidar_message
            lidar_check = payload.get("lidar_check")
            if isinstance(lidar_check, dict):
                self._lidar_check = dict(lidar_check)
            postprocess = payload.get("postprocess")
            if isinstance(postprocess, dict):
                self._postprocess = dict(postprocess)
            self._seq += 1
            self._updated_at = time.time()

    def handle_command(self, command: str, payload: Optional[dict[str, Any]] = None) -> MappingCommandResult:
        normalized = command.strip()
        if normalized not in VALID_MAPPING_COMMANDS:
            return self._reject(normalized, "未知建图指令")

        request = MappingCommandRequest(
            command=normalized,
            session_name=str((payload or {}).get("session_name", "")).strip(),
            save_directory=str((payload or {}).get("save_directory", "")).strip(),
            session_id=str((payload or {}).get("session_id", "")).strip(),
            preset=str((payload or {}).get("preset", "")).strip(),
        )
        if normalized == "start_lidar":
            return self._start_lidar(request)
        if normalized == "stop_lidar":
            return self._stop_lidar(request)
        if normalized == "check_lidar":
            return self._check_lidar(request)
        if normalized == "start":
            return self._start(request)
        if normalized == "stop":
            return self._stop(request)
        if normalized == "save":
            return self._save(request)
        if normalized == "rerun_postprocess":
            return self._rerun_postprocess(request)
        return self._reset_error(request)

    def _start(self, request: MappingCommandRequest) -> MappingCommandResult:
        with self._lock:
            if self._state not in {"idle", "stopped", "error"}:
                return self._reject_unlocked(request.command, f"当前不能开始建图")
            if not self._lidar_valid:
                return self._reject_unlocked(request.command, "雷达数据未验证，不能开始建图")
            self._session_name = request.session_name
            self._save_directory = request.save_directory
            self._transition_unlocked("starting", "正在请求启动建图")
        result = self._backend.start(request)
        with self._lock:
            next_state = "starting" if result.accepted and _is_async_result(result) else "mapping" if result.accepted else "error"
            self._transition_unlocked(next_state, result.message, request.command, result)
            return self._result_unlocked(request.command, result.accepted, result.message, result.details)

    def _start_lidar(self, request: MappingCommandRequest) -> MappingCommandResult:
        with self._lock:
            if self._state in {"mapping", "saving", "stopping"}:
                return self._reject_unlocked(request.command, "建图运行中，不能单独启动雷达")
            self._lidar_state = "starting"
            self._lidar_valid = False
            self._lidar_checking = False
            self._lidar_message = "正在请求启动雷达"
            self._transition_unlocked(self._state, self._lidar_message)
        result = self._backend.start_lidar(request)
        with self._lock:
            if not result.accepted:
                self._lidar_state = "disconnected"
                self._lidar_message = result.message
                self._lidar_checking = False
            self._transition_unlocked(self._state, result.message, request.command, result)
            return self._result_unlocked(request.command, result.accepted, result.message, result.details)

    def _stop_lidar(self, request: MappingCommandRequest) -> MappingCommandResult:
        with self._lock:
            if self._state in {"starting", "mapping", "saving", "stopping"}:
                return self._reject_unlocked(request.command, "建图运行中，不能关闭雷达")
            self._lidar_state = "stopping"
            self._lidar_valid = False
            self._lidar_checking = False
            self._lidar_message = "正在请求关闭雷达"
            self._transition_unlocked(self._state, self._lidar_message)
        result = self._backend.stop_lidar(request)
        with self._lock:
            if not result.accepted:
                self._lidar_message = result.message
                self._lidar_state = "disconnected"
            if result.accepted:
                self._lidar_state = "stopping"
            self._transition_unlocked(self._state, result.message, request.command, result)
            return self._result_unlocked(request.command, result.accepted, result.message, result.details)

    def _check_lidar(self, request: MappingCommandRequest) -> MappingCommandResult:
        with self._lock:
            if self._state in {"mapping", "saving", "stopping"}:
                return self._reject_unlocked(request.command, "建图运行中，不能检测雷达")
            self._lidar_state = "checking"
            self._lidar_valid = False
            self._lidar_checking = True
            self._lidar_message = "正在检测雷达"
            self._transition_unlocked(self._state, self._lidar_message)
        result = self._backend.check_lidar(request)
        with self._lock:
            self._transition_unlocked(self._state, result.message, request.command, result)
            return self._result_unlocked(request.command, result.accepted, result.message, result.details)

    def _stop(self, request: MappingCommandRequest) -> MappingCommandResult:
        with self._lock:
            if self._state not in {"starting", "mapping"}:
                return self._reject_unlocked(request.command, f"当前不能停止建图")
            self._transition_unlocked("stopping", "正在请求停止建图")
        result = self._backend.stop(request)
        with self._lock:
            next_state = "stopping" if result.accepted and _is_async_result(result) else "stopped" if result.accepted else "error"
            self._transition_unlocked(next_state, result.message, request.command, result)
            return self._result_unlocked(request.command, result.accepted, result.message, result.details)

    def _save(self, request: MappingCommandRequest) -> MappingCommandResult:
        with self._lock:
            if self._state != "stopped":
                return self._reject_unlocked(request.command, f"当前不能保存地图")
            if request.save_directory:
                self._save_directory = request.save_directory
            self._transition_unlocked("saving", "正在请求保存地图")
        result = self._backend.save(request)
        with self._lock:
            next_state = "saving" if result.accepted and _is_async_result(result) else "stopped" if result.accepted else "error"
            self._transition_unlocked(next_state, result.message, request.command, result)
            return self._result_unlocked(request.command, result.accepted, result.message, result.details)

    def _rerun_postprocess(self, request: MappingCommandRequest) -> MappingCommandResult:
        with self._lock:
            if self._state in {"starting", "mapping", "saving", "stopping"}:
                return self._reject_unlocked(request.command, "建图运行中，不能重跑后处理")
            if not request.session_id:
                return self._reject_unlocked(request.command, "缺少地图会话")
            self._transition_unlocked("saving", "正在请求重跑后处理")
        result = self._backend.rerun_postprocess(request)
        with self._lock:
            next_state = "saving" if result.accepted and _is_async_result(result) else "stopped" if result.accepted else "error"
            self._transition_unlocked(next_state, result.message, request.command, result)
            return self._result_unlocked(request.command, result.accepted, result.message, result.details)

    def _reset_error(self, request: MappingCommandRequest) -> MappingCommandResult:
        with self._lock:
            if self._state != "error":
                return self._reject_unlocked(request.command, f"当前没有异常需要重置")
            self._transition_unlocked("idle", "异常已清除", request.command)
            return self._result_unlocked(request.command, True, self._message)

    def _reject(self, command: str, message: str) -> MappingCommandResult:
        with self._lock:
            return self._reject_unlocked(command, message)

    def _reject_unlocked(self, command: str, message: str) -> MappingCommandResult:
        self._last_command = command
        self._last_result = message
        self._message = message
        self._seq += 1
        self._updated_at = time.time()
        return self._result_unlocked(command, False, message)

    def _transition_unlocked(
        self,
        state: str,
        message: str,
        command: Optional[str] = None,
        result: Optional[MappingBackendResult] = None,
    ) -> None:
        if state not in VALID_MAPPING_STATES:
            raise ValueError(f"invalid mapping state: {state}")
        self._state = state
        self._message = message
        if command:
            self._last_command = command
            self._last_result = result.message if result else message
        self._seq += 1
        self._updated_at = time.time()

    def _result_unlocked(
        self,
        command: str,
        accepted: bool,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> MappingCommandResult:
        return MappingCommandResult(
            command=command,
            accepted=accepted,
            state=self._state,
            message=message,
            details=details,
        )

    def _allowed_commands_unlocked(self) -> set[str]:
        if self._state in {"idle", "stopped", "error"}:
            commands = {"start_lidar", "stop_lidar", "check_lidar"}
            if self._lidar_valid:
                commands.add("start")
        elif self._state in {"starting", "mapping"}:
            commands = {"stop"}
        else:
            commands = set()
        if self._state == "stopped":
            commands.add("save")
        if self._state in {"idle", "stopped", "error"}:
            commands.add("rerun_postprocess")
        if self._state == "error":
            commands.add("reset_error")
        return commands


def _is_async_result(result: MappingBackendResult) -> bool:
    return bool((result.details or {}).get("async"))
