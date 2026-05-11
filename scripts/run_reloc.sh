#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/sunray_env.sh"
source_ros_env

RELOC_MAP_FILE="${RELOC_MAP_FILE:-${SUNRAY_SLAM_ROOT}/data/office.ply}"
RELOC_TOPIC_WAIT_TIMEOUT_SEC="${RELOC_TOPIC_WAIT_TIMEOUT_SEC:-300}"
RELOC_MIN_BOOT_AGE_SEC="${RELOC_MIN_BOOT_AGE_SEC:-45}"
RELOC_LIVOX_SETTLE_SEC="${RELOC_LIVOX_SETTLE_SEC:-10}"
RELOC_FASTLIO_SETTLE_SEC="${RELOC_FASTLIO_SETTLE_SEC:-5}"
RELOC_FASTLIO_CONFIG_FILE="${RELOC_FASTLIO_CONFIG_FILE:-mid360.yaml}"
RELOC_LIVOX_HOST_IFACE="${RELOC_LIVOX_HOST_IFACE:-${LIVOX_HOST_IFACE:-eth0}}"
RELOC_LIVOX_HOST_IP="${RELOC_LIVOX_HOST_IP:-${LIVOX_HOST_IP:-192.168.1.5}}"
RELOC_STARTUP_TIMING_FILE="${RELOC_STARTUP_TIMING_FILE:-${SUNRAY_RUN_DIR}/startup_timing.log}"

log() {
  printf '[sunray-reloc] %s\n' "$*"
}

monotonic_ms() { awk '{printf "%d\n", $1 * 1000}' /proc/uptime; }
SCRIPT_START_MONOTONIC_MS="$(monotonic_ms)"

record_timing() {
  local stage="$1" epoch_ms now_ms elapsed_ms
  epoch_ms="$(date +%s%3N)"
  now_ms="$(monotonic_ms)"
  elapsed_ms="$((now_ms - SCRIPT_START_MONOTONIC_MS))"
  printf '%s epoch_ms=%s since_boot_ms=%s elapsed_ms=%s\n' "${stage}" "${epoch_ms}" "${now_ms}" "${elapsed_ms}" >> "${RELOC_STARTUP_TIMING_FILE}"
  log "timing ${stage} elapsed_ms=${elapsed_ms}"
}

start_group() {
  local name="$1"
  local cmd="$2"
  local pid_file="${SUNRAY_RUN_DIR}/${name}.pid"
  local log_file="${SUNRAY_LOG_DIR}/${name}.log"
  setsid bash -lc "${cmd}" > >(tee -a "${log_file}" | sed -u "s/^/[${name}] /") 2>&1 &
  local pid=$!
  printf '%s\n' "${pid}" > "${pid_file}"
  log "started ${name} pgid=${pid}"
}

stop_group() {
  local name="$1"
  local pid_file="${SUNRAY_RUN_DIR}/${name}.pid"
  [[ -f "${pid_file}" ]] || return 0
  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  [[ -n "${pid}" ]] || return 0
  kill -TERM "-${pid}" >/dev/null 2>&1 || true
}

wait_for_min_boot_age() {
  local min_boot_age_sec="$1"
  [[ "${min_boot_age_sec}" =~ ^[0-9]+$ ]] || min_boot_age_sec=0
  while true; do
    local uptime_sec
    uptime_sec="$(awk '{printf "%d\n", $1}' /proc/uptime)"
    if (( uptime_sec >= min_boot_age_sec )); then
      return 0
    fi
    log "waiting for boot age ${min_boot_age_sec}s (current=${uptime_sec}s)"
    sleep 1
  done
}

wait_for_host_ip() {
  local timeout_sec="$1"
  local deadline=$((SECONDS + timeout_sec))
  log "waiting for ${RELOC_LIVOX_HOST_IFACE} host ip ${RELOC_LIVOX_HOST_IP}"
  while (( SECONDS < deadline )); do
    if ip -4 addr show dev "${RELOC_LIVOX_HOST_IFACE}" 2>/dev/null | grep -q "${RELOC_LIVOX_HOST_IP}/" &&
       [[ "$(cat "/sys/class/net/${RELOC_LIVOX_HOST_IFACE}/carrier" 2>/dev/null || echo 0)" = "1" ]]; then
      return 0
    fi
    sleep 1
  done
  log "timed out waiting for ${RELOC_LIVOX_HOST_IFACE} carrier and host ip ${RELOC_LIVOX_HOST_IP}"
  exit 1
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
  timeout "${timeout_sec}" bash -lc "ros2 topic echo '${topic}' | head -n 1 >/dev/null" >/dev/null 2>&1 || {
    log "timed out waiting for first message on ${topic}"
    exit 1
  }
}

cleanup() {
  stop_group open3d_loc
  stop_group fastlio
  stop_group livox
  "${SUNRAY_SLAM_ROOT}/scripts/stop_localization.sh" || true
}

trap 'cleanup; exit 0' TERM INT

if [[ ! -f "${RELOC_MAP_FILE}" ]]; then
  log "missing reloc map file: ${RELOC_MAP_FILE}"
  exit 1
fi

log "map file: ${RELOC_MAP_FILE}"
mkdir -p "${SUNRAY_RUN_DIR}" "${SUNRAY_LOG_DIR}"
: > "${RELOC_STARTUP_TIMING_FILE}"
: > "${SUNRAY_LOG_DIR}/livox.log"
: > "${SUNRAY_LOG_DIR}/fastlio.log"
: > "${SUNRAY_LOG_DIR}/open3d_loc.log"

record_timing script_start
wait_for_host_ip "${RELOC_TOPIC_WAIT_TIMEOUT_SEC}"
record_timing livox_host_ip_ready
wait_for_min_boot_age "${RELOC_MIN_BOOT_AGE_SEC}"
record_timing min_boot_age_ready

start_group livox 'exec ros2 launch livox_ros_driver2 msg_MID360s_launch.py'
record_timing livox_started
wait_for_topic /livox/lidar "${RELOC_TOPIC_WAIT_TIMEOUT_SEC}"
wait_for_topic /livox/imu "${RELOC_TOPIC_WAIT_TIMEOUT_SEC}"
record_timing livox_topics_ready
wait_for_topic_message /livox/lidar "${RELOC_TOPIC_WAIT_TIMEOUT_SEC}"
wait_for_topic_message /livox/imu "${RELOC_TOPIC_WAIT_TIMEOUT_SEC}"
record_timing livox_messages_ready
sleep "${RELOC_LIVOX_SETTLE_SEC}"
record_timing livox_settle_complete

start_group fastlio "exec ros2 launch fast_lio mapping.launch.py rviz:=false start_livox_driver:=false config_file:='${RELOC_FASTLIO_CONFIG_FILE}'"
record_timing fastlio_started
wait_for_topic /Odometry_loc "${RELOC_TOPIC_WAIT_TIMEOUT_SEC}"
wait_for_topic /cloud_registered_1 "${RELOC_TOPIC_WAIT_TIMEOUT_SEC}"
record_timing fastlio_topics_ready
wait_for_topic_message /Odometry_loc "${RELOC_TOPIC_WAIT_TIMEOUT_SEC}"
wait_for_topic_message /cloud_registered_1 "${RELOC_TOPIC_WAIT_TIMEOUT_SEC}"
record_timing fastlio_messages_ready
sleep "${RELOC_FASTLIO_SETTLE_SEC}"
record_timing fastlio_settle_complete

start_group open3d_loc "exec ros2 launch open3d_loc open3d_loc_g1.launch.py rviz:=false map_file:='${RELOC_MAP_FILE}'"
record_timing open3d_loc_started

while true; do
  for name in livox fastlio open3d_loc; do
    pid_file="${SUNRAY_RUN_DIR}/${name}.pid"
    [[ -f "${pid_file}" ]] || { log "missing pid file for ${name}"; exit 1; }
    pid="$(cat "${pid_file}")"
    kill -0 "${pid}" 2>/dev/null || { log "${name} pgid=${pid} exited"; exit 1; }
  done
  sleep 2
done
