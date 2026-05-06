#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/sunray_env.sh"
source_ros_env

log() {
  printf '[sunray-fastlio-restart] %s\n' "$*"
}

stop_fastlio() {
  local pid_file="${SUNRAY_RUN_DIR}/fastlio.pid"
  if [[ ! -f "${pid_file}" ]]; then
    return
  fi

  local pid
  pid="$(cat "${pid_file}")"
  if kill -0 "${pid}" 2>/dev/null; then
    log "stopping fastlio pgid=${pid}"
    kill -TERM -- "-${pid}" 2>/dev/null || true
    for _ in $(seq 1 10); do
      if ! kill -0 "${pid}" 2>/dev/null; then
        break
      fi
      sleep 1
    done
    if kill -0 "${pid}" 2>/dev/null; then
      log "force killing fastlio pgid=${pid}"
      kill -KILL -- "-${pid}" 2>/dev/null || true
    fi
  fi

  rm -f "${pid_file}"
}

start_fastlio() {
  local pid_file="${SUNRAY_RUN_DIR}/fastlio.pid"
  setsid bash -lc 'exec ros2 launch fast_lio mapping.launch.py rviz:=false start_livox_driver:=false' >>"${SUNRAY_LOG_DIR}/fastlio.log" 2>&1 &
  local pid=$!
  printf '%s\n' "${pid}" > "${pid_file}"
  log "started fastlio pgid=${pid}"
}

stop_fastlio
start_fastlio
