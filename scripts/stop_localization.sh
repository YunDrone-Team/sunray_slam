#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/sunray_env.sh"

log() {
  printf '[sunray-stop] %s\n' "$*"
}

stop_group() {
  local name="$1"
  local pid_file="${SUNRAY_RUN_DIR}/${name}.pid"
  if [[ ! -f "${pid_file}" ]]; then
    return
  fi

  local pid
  pid="$(cat "${pid_file}")"
  if kill -0 "${pid}" 2>/dev/null; then
    log "stopping ${name} pgid=${pid}"
    kill -TERM -- "-${pid}" 2>/dev/null || true
    for _ in $(seq 1 10); do
      if ! kill -0 "${pid}" 2>/dev/null; then
        break
      fi
      sleep 1
    done
    if kill -0 "${pid}" 2>/dev/null; then
      log "force killing ${name} pgid=${pid}"
      kill -KILL -- "-${pid}" 2>/dev/null || true
    fi
  fi

  rm -f "${pid_file}"
}

stop_group livox
stop_group fastlio
stop_group roscore
