#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/sunray_env.sh"
source_ros_env

RELOC_MAP_FILE="${RELOC_MAP_FILE:-${SUNRAY_SLAM_ROOT}/data/office.ply}"

log() {
  printf '[sunray-reloc] %s\n' "$*"
}

if [[ ! -f "${RELOC_MAP_FILE}" ]]; then
  log "missing reloc map file: ${RELOC_MAP_FILE}"
  exit 1
fi

log "map file: ${RELOC_MAP_FILE}"

exec ros2 launch open3d_loc localization_3d_g1.launch.py \
  start_livox_driver:=true \
  rviz:=false \
  map_file:="${RELOC_MAP_FILE}"
