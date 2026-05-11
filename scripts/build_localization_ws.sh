#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/sunray_env.sh"

SRC_DIR="${LOCALIZATION_WS_ROOT}/src"
LIVOX_WS_ROOT="${SRC_DIR}/livox_ros_driver2"

log() {
  printf '[sunray-build] %s\n' "$*"
}

require_dir() {
  local path="$1"
  if [[ ! -d "${path}" ]]; then
    printf '[sunray-build] missing required directory: %s\n' "${path}" >&2
    exit 1
  fi
}

require_dir "${FAST_LIO_ROOT}"
require_dir "${OPEN3D_LOC_ROOT}"
require_dir "${LIVOX_ROOT}"
require_dir "${LIVOX_SDK2_ROOT}"

if [[ ! -f /usr/local/lib/liblivox_lidar_sdk_shared.so ]]; then
  printf '[sunray-build] missing Livox-SDK2 shared library: /usr/local/lib/liblivox_lidar_sdk_shared.so\n' >&2
  printf '[sunray-build] install it with: scripts/install_livox_sdk2.sh\n' >&2
  exit 1
fi

if [[ ! -f /usr/local/include/livox_lidar_api.h ]]; then
  printf '[sunray-build] missing Livox-SDK2 header: /usr/local/include/livox_lidar_api.h\n' >&2
  printf '[sunray-build] install it with: scripts/install_livox_sdk2.sh\n' >&2
  exit 1
fi

if [[ ! -f "${LIVOX_ROOT}/package_ROS2.xml" ]]; then
  printf '[sunray-build] missing Livox ROS2 package file: %s\n' "${LIVOX_ROOT}/package_ROS2.xml" >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  printf '[sunray-build] missing required command: rsync\n' >&2
  exit 1
fi

if [[ ! -f "${ROS_SETUP_BASH}" ]]; then
  printf '[sunray-build] missing ROS setup: %s\n' "${ROS_SETUP_BASH}" >&2
  exit 1
fi

if [[ -z "${Open3D_DIR:-}" ]]; then
  for candidate in \
    "${HOME}/open3d141/lib/cmake/Open3D" \
    "${HOME}/open3d/lib/cmake/Open3D" \
    /usr/local/lib/cmake/Open3D \
    /usr/lib/cmake/Open3D \
    /usr/lib/aarch64-linux-gnu/cmake/Open3D \
    /usr/lib/x86_64-linux-gnu/cmake/Open3D; do
    if [[ -f "${candidate}/Open3DConfig.cmake" || -f "${candidate}/open3d-config.cmake" ]]; then
      export Open3D_DIR="${candidate}"
      log "auto-detected Open3D_DIR: ${Open3D_DIR}"
      break
    fi
  done
fi

mkdir -p "${SRC_DIR}"
rm -f "${SRC_DIR}/FAST_LIO"
ln -sfn "${FAST_LIO_ROOT}" "${SRC_DIR}/fast_lio"
ln -sfn "${OPEN3D_LOC_ROOT}" "${SRC_DIR}/open3d_loc"
rm -rf "${LIVOX_WS_ROOT}"
rsync -a \
  --exclude='.git' \
  --exclude='.git/' \
  --exclude='build/' \
  --exclude='install/' \
  --exclude='log/' \
  "${LIVOX_ROOT}/" "${LIVOX_WS_ROOT}/"
cp -f "${LIVOX_WS_ROOT}/package_ROS2.xml" "${LIVOX_WS_ROOT}/package.xml"

log "workspace: ${LOCALIZATION_WS_ROOT}"
log "source packages: ${SUNRAY_SLAM_ROOT}"
log "source ROS: ${ROS_SETUP_BASH}"

set +u
source "${ROS_SETUP_BASH}"
set -u

cd "${LOCALIZATION_WS_ROOT}"
cmake_args=(-DROS_EDITION=ROS2)
if [[ -n "${ROS_DISTRO:-}" ]]; then
  cmake_args+=("-DDISTRO_ROS=${ROS_DISTRO}")
fi
if [[ -n "${Open3D_DIR:-}" ]]; then
  cmake_args+=("-DOpen3D_DIR=${Open3D_DIR}")
fi

colcon build --symlink-install --cmake-args "${cmake_args[@]}" "$@"
