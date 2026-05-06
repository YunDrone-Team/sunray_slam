#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/sunray_env.sh"
source_ros_env

LIVOX_TOPIC_WAIT_TIMEOUT_SEC="${LIVOX_TOPIC_WAIT_TIMEOUT_SEC:-300}"
LIVOX_SETTLE_SEC="${LIVOX_SETTLE_SEC:-3}"
LIVOX_HOST_IFACE="${LIVOX_HOST_IFACE:-eth0}"
LIVOX_HOST_IP="${LIVOX_HOST_IP:-192.168.1.5}"
STARTUP_TIMING_FILE="${STARTUP_TIMING_FILE:-${SUNRAY_RUN_DIR}/startup_timing.log}"

monotonic_ms() { awk '{printf "%d\n", $1 * 1000}' /proc/uptime; }
SCRIPT_START_MONOTONIC_MS="$(monotonic_ms)"

log() { printf '[sunray-fastlio] %s\n' "$*"; }

record_timing() {
  local stage="$1" epoch_ms now_ms elapsed_ms
  epoch_ms="$(date +%s%3N)"
  now_ms="$(monotonic_ms)"
  elapsed_ms="$((now_ms - SCRIPT_START_MONOTONIC_MS))"
  printf '%s epoch_ms=%s since_boot_ms=%s elapsed_ms=%s\n' "${stage}" "${epoch_ms}" "${now_ms}" "${elapsed_ms}" >> "${STARTUP_TIMING_FILE}"
  log "timing ${stage} elapsed_ms=${elapsed_ms}"
}

start_group() {
  local name="$1"
  local cmd="$2"
  local pid_file="${SUNRAY_RUN_DIR}/${name}.pid"
  setsid bash -lc "${cmd}" >>"${SUNRAY_LOG_DIR}/${name}.log" 2>&1 &
  local pid=$!
  printf '%s\n' "${pid}" > "${pid_file}"
  log "started ${name} pgid=${pid}"
}

wait_for_topic() {
  local topic="$1"
  local timeout_sec="$2"
  local deadline=$((SECONDS + timeout_sec))
  log "waiting for topic ${topic}"
  while (( SECONDS < deadline )); do
    if ros2 topic list 2>/dev/null | grep -qx "${topic}"; then
      return 0
    fi
    sleep 1
  done
  log "timed out waiting for topic ${topic}"
  exit 1
}

wait_for_topic_message() {
  local topic="$1"
  local timeout_sec="$2"
  log "waiting for first message on ${topic}"
  timeout "${timeout_sec}" ros2 topic echo --once "${topic}" >/dev/null 2>&1 || {
    log "timed out waiting for first message on ${topic}"
    exit 1
  }
}

wait_for_host_ip() {
  local timeout_sec="$1"
  local deadline=$((SECONDS + timeout_sec))
  log "waiting for ${LIVOX_HOST_IFACE} host ip ${LIVOX_HOST_IP}"
  while (( SECONDS < deadline )); do
    if ip -4 addr show dev "${LIVOX_HOST_IFACE}" 2>/dev/null | grep -q "${LIVOX_HOST_IP}/"; then
      return 0
    fi
    sleep 1
  done
  log "timed out waiting for ${LIVOX_HOST_IFACE} host ip ${LIVOX_HOST_IP}"
  exit 1
}

cleanup() {
  "${SUNRAY_SLAM_ROOT}/scripts/stop_localization.sh" || true
}

trap 'cleanup; exit 0' TERM INT

mkdir -p "${SUNRAY_RUN_DIR}" "${SUNRAY_LOG_DIR}"
: > "${STARTUP_TIMING_FILE}"
: > "${SUNRAY_LOG_DIR}/livox.log"
: > "${SUNRAY_LOG_DIR}/fastlio.log"

record_timing script_start
wait_for_host_ip "${LIVOX_TOPIC_WAIT_TIMEOUT_SEC}"
record_timing livox_host_ip_ready
start_group livox 'exec ros2 launch livox_ros_driver2 msg_MID360s_launch.py'
record_timing livox_started
wait_for_topic /livox/lidar "${LIVOX_TOPIC_WAIT_TIMEOUT_SEC}"
wait_for_topic /livox/imu "${LIVOX_TOPIC_WAIT_TIMEOUT_SEC}"
record_timing livox_topics_ready
wait_for_topic_message /livox/lidar "${LIVOX_TOPIC_WAIT_TIMEOUT_SEC}"
wait_for_topic_message /livox/imu "${LIVOX_TOPIC_WAIT_TIMEOUT_SEC}"
record_timing livox_messages_ready
sleep "${LIVOX_SETTLE_SEC}"
record_timing livox_settle_complete
start_group fastlio 'exec ros2 launch fast_lio mapping.launch.py rviz:=false start_livox_driver:=false'
record_timing fastlio_started

while true; do
  for name in livox fastlio; do
    pid_file="${SUNRAY_RUN_DIR}/${name}.pid"
    [[ -f "${pid_file}" ]] || { log "missing pid file for ${name}"; exit 1; }
    pid="$(cat "${pid_file}")"
    kill -0 "${pid}" 2>/dev/null || { log "${name} pgid=${pid} exited"; exit 1; }
  done
  sleep 2
done
