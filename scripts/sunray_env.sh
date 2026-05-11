#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUNRAY_SLAM_ROOT="${SUNRAY_SLAM_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"

ENV_FILE="${SUNRAY_ENV_FILE:-}"
if [[ -n "${ENV_FILE}" ]]; then
  if [[ ! -f "${ENV_FILE}" ]]; then
    printf '[sunray-env] missing env file: %s\n' "${ENV_FILE}" >&2
    exit 1
  fi
  set -a
  source "${ENV_FILE}"
  set +a
fi

if [[ -z "${ROS_SETUP_BASH:-}" ]]; then
  if [[ -n "${ROS_DISTRO:-}" && -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]]; then
    ROS_SETUP_BASH="/opt/ros/${ROS_DISTRO}/setup.bash"
  elif [[ -f /opt/ros/humble/setup.bash ]]; then
    ROS_SETUP_BASH=/opt/ros/humble/setup.bash
  elif [[ -f /opt/ros/foxy/setup.bash ]]; then
    ROS_SETUP_BASH=/opt/ros/foxy/setup.bash
  else
    ROS_SETUP_BASH=/opt/ros/humble/setup.bash
  fi
fi
: "${ROS_SETUP_BASH:?ROS_SETUP_BASH is required}"
: "${LOCALIZATION_WS_ROOT:=${SUNRAY_SLAM_ROOT}/.runtime/localization_ws}"
: "${LOCALIZATION_WS_SETUP_BASH:=${LOCALIZATION_WS_ROOT}/install/setup.bash}"
: "${SUNRAY_RUN_DIR:=${SUNRAY_SLAM_ROOT}/.runtime/run}"
: "${SUNRAY_LOG_DIR:=${SUNRAY_SLAM_ROOT}/.runtime/logs}"

FAST_LIO_ROOT="${FAST_LIO_ROOT:-${SUNRAY_SLAM_ROOT}/fast_lio}"
OPEN3D_LOC_ROOT="${OPEN3D_LOC_ROOT:-${SUNRAY_SLAM_ROOT}/open3d_loc}"
LIVOX_ROOT="${LIVOX_ROOT:-${SUNRAY_SLAM_ROOT}/livox_ros_driver2}"
LIVOX_SDK2_ROOT="${LIVOX_SDK2_ROOT:-${SUNRAY_SLAM_ROOT}/Livox-SDK2}"

mkdir -p "${SUNRAY_RUN_DIR}" "${SUNRAY_LOG_DIR}"

source_ros_env() {
  if [[ ! -f "${ROS_SETUP_BASH}" ]]; then
    printf '[sunray-env] missing ROS setup: %s\n' "${ROS_SETUP_BASH}" >&2
    exit 1
  fi
  if [[ ! -f "${LOCALIZATION_WS_SETUP_BASH}" ]]; then
    printf '[sunray-env] missing localization workspace setup: %s\n' "${LOCALIZATION_WS_SETUP_BASH}" >&2
    exit 1
  fi
  set +u
  source "${ROS_SETUP_BASH}"
  source "${LOCALIZATION_WS_SETUP_BASH}"
  set -u
}
