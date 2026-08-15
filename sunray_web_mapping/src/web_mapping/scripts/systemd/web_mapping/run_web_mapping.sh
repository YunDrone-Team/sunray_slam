#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_MAPPING_REPO="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
WORKSPACE="${WEB_MAPPING_WORKSPACE:-}"

find_workspace_root() {
  local current="${WEB_MAPPING_REPO}"
  while [[ "${current}" != "/" ]]; do
    if [[ -d "${current}/install" ]] && [[ -d "${current}/src" ]]; then
      printf '%s\n' "${current}"
      return 0
    fi
    current="$(dirname "${current}")"
  done
  printf '%s\n' "${WEB_MAPPING_REPO}"
}

if [[ -z "${WORKSPACE}" ]]; then
  WORKSPACE="$(find_workspace_root)"
fi

WORKSPACE_SETUP="${WEB_MAPPING_SETUP_FILE:-${WORKSPACE}/install/local_setup.bash}"
LAUNCH_PACKAGE="${WEB_MAPPING_LAUNCH_PACKAGE:-web_mapping}"
LAUNCH_FILE="${WEB_MAPPING_LAUNCH_FILE:-web_mapping.launch.py}"
LAUNCH_ARGS_MODE="${WEB_MAPPING_LAUNCH_ARGS_MODE:-standalone}"

if [[ ! -d "${WORKSPACE}" ]]; then
  echo "web_mapping workspace does not exist: ${WORKSPACE}" >&2
  exit 1
fi

if [[ ! -f "${WORKSPACE_SETUP}" ]]; then
  echo "Workspace setup file does not exist: ${WORKSPACE_SETUP}" >&2
  echo "Build the workspace first, for example:" >&2
  echo "  cd ${WORKSPACE} && source /opt/ros/<distro>/setup.bash && colcon build --symlink-install" >&2
  exit 1
fi

cd "${WORKSPACE}"

resolve_ros_setup() {
  if [[ -n "${WEB_MAPPING_ROS_SETUP:-}" ]]; then
    printf '%s\n' "${WEB_MAPPING_ROS_SETUP}"
    return 0
  fi

  if [[ -n "${ROS_DISTRO:-}" ]]; then
    printf '/opt/ros/%s/setup.bash\n' "${ROS_DISTRO}"
    return 0
  fi

  if [[ -f "${WORKSPACE}/install/setup.bash" ]]; then
    local prefix
    while IFS= read -r prefix; do
      if [[ -n "${prefix}" && -f "${prefix}/setup.bash" ]] && setup_is_ros2 "${prefix}/setup.bash"; then
        printf '%s/setup.bash\n' "${prefix}"
        return 0
      fi
    done < <(awk -F'"' '/^COLCON_CURRENT_PREFIX="\/opt\/ros\// {print $2}' "${WORKSPACE}/install/setup.bash")
  fi

  local setup
  for setup in /opt/ros/*/setup.bash; do
    [[ -f "${setup}" ]] || continue
    if setup_is_ros2 "${setup}"; then
      printf '%s\n' "${setup}"
      return 0
    fi
  done

  return 1
}

clean_ros_env() {
  unset ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION ROS_PACKAGE_PATH ROS_ETC_DIR
  unset ROS_MASTER_URI ROS_ROOT ROSLISP_PACKAGE_DIRECTORIES
  unset AMENT_PREFIX_PATH COLCON_PREFIX_PATH CMAKE_PREFIX_PATH PYTHONPATH
}

setup_is_ros2() {
  local setup="$1"
  local version
  set +u
  clean_ros_env
  # shellcheck source=/dev/null
  source "${setup}"
  version="${ROS_VERSION:-}"
  clean_ros_env
  set -u
  [[ "${version}" == "2" ]]
}

ROS_SETUP="$(resolve_ros_setup || true)"
if [[ -z "${ROS_SETUP}" || ! -f "${ROS_SETUP}" ]]; then
  echo "Unable to find a ROS 2 setup.bash. Set WEB_MAPPING_ROS_SETUP or ROS_DISTRO." >&2
  exit 1
fi
echo "Using ROS setup: ${ROS_SETUP}"

# systemd does not load ~/.bashrc, so source ROS explicitly. Some ROS 2 setup
# scripts read optional variables that may be unset, so disable nounset only
# while sourcing them.
set +u
clean_ros_env
# shellcheck source=/dev/null
source "${ROS_SETUP}"
# shellcheck source=/dev/null
source "${WORKSPACE_SETUP}"
set -u

if [[ "${ROS_VERSION:-}" != "2" ]]; then
  echo "Resolved setup is not a ROS 2 environment: ${ROS_SETUP}" >&2
  exit 1
fi

if [[ -n "${WEB_MAPPING_ROS_DOMAIN_ID:-}" ]]; then
  export ROS_DOMAIN_ID="${WEB_MAPPING_ROS_DOMAIN_ID}"
fi

if [[ -n "${WEB_MAPPING_ROS_LOCALHOST_ONLY:-}" ]]; then
  export ROS_LOCALHOST_ONLY="${WEB_MAPPING_ROS_LOCALHOST_ONLY}"
fi

if ! ros2 pkg prefix web_mapping >/dev/null 2>&1; then
  echo "ROS package web_mapping is not visible after sourcing ${WORKSPACE_SETUP}" >&2
  exit 1
fi

if ! ros2 pkg prefix "${LAUNCH_PACKAGE}" >/dev/null 2>&1; then
  echo "ROS package ${LAUNCH_PACKAGE} is not visible after sourcing ${WORKSPACE_SETUP}" >&2
  exit 1
fi

map_history_root="${WEB_MAPPING_MAP_HISTORY_ROOT:-maps}"
if [[ "${map_history_root}" = /* ]]; then
  mkdir -p "${map_history_root}"
else
  mkdir -p "${WORKSPACE}/${map_history_root}"
fi

launch_args=()

add_launch_arg() {
  local name="$1"
  local value="$2"
  if [[ -n "${value}" ]]; then
    launch_args+=("${name}:=${value}")
  fi
}

case "${LAUNCH_ARGS_MODE}" in
  standalone)
    add_launch_arg "use_sim_time" "${WEB_MAPPING_USE_SIM_TIME:-}"
    add_launch_arg "map_history_root" "${WEB_MAPPING_MAP_HISTORY_ROOT:-}"
    add_launch_arg "map_history_limit" "${WEB_MAPPING_MAP_HISTORY_LIMIT:-}"
    add_launch_arg "host" "${WEB_MAPPING_WEB_HOST:-}"
    add_launch_arg "port" "${WEB_MAPPING_WEB_PORT:-}"
    add_launch_arg "raw_cloud_topic" "${WEB_MAPPING_RAW_CLOUD_TOPIC:-}"
    add_launch_arg "optimized_cloud_topic" "${WEB_MAPPING_OPTIMIZED_CLOUD_TOPIC:-}"
    add_launch_arg "map_cloud_topic" "${WEB_MAPPING_MAP_CLOUD_TOPIC:-}"
    add_launch_arg "pose_topic" "${WEB_MAPPING_POSE_TOPIC:-}"
    add_launch_arg "raw_path_topic" "${WEB_MAPPING_RAW_PATH_TOPIC:-}"
    add_launch_arg "optimized_path_topic" "${WEB_MAPPING_OPTIMIZED_PATH_TOPIC:-}"
    add_launch_arg "imu_topic" "${WEB_MAPPING_IMU_TOPIC:-}"
    add_launch_arg "lidar_status_topic" "${WEB_MAPPING_LIDAR_STATUS_TOPIC:-}"
    add_launch_arg "mapping_command_topic" "${WEB_MAPPING_COMMAND_TOPIC:-}"
    add_launch_arg "mapping_status_topic" "${WEB_MAPPING_STATUS_TOPIC:-}"
    add_launch_arg "use_broker_backend" "${WEB_MAPPING_USE_BROKER_BACKEND:-}"
    add_launch_arg "max_points_per_cloud" "${WEB_MAPPING_MAX_POINTS_PER_CLOUD:-}"
    add_launch_arg "max_raw_points_per_cloud" "${WEB_MAPPING_MAX_RAW_POINTS_PER_CLOUD:-}"
    add_launch_arg "max_optimized_points_per_cloud" "${WEB_MAPPING_MAX_OPTIMIZED_POINTS_PER_CLOUD:-}"
    add_launch_arg "max_map_points_per_cloud" "${WEB_MAPPING_MAX_MAP_POINTS_PER_CLOUD:-}"
    add_launch_arg "min_cloud_interval_sec" "${WEB_MAPPING_MIN_CLOUD_INTERVAL_SEC:-}"
    add_launch_arg "min_raw_cloud_interval_sec" "${WEB_MAPPING_MIN_RAW_CLOUD_INTERVAL_SEC:-}"
    add_launch_arg "min_map_interval_sec" "${WEB_MAPPING_MIN_MAP_INTERVAL_SEC:-}"
    add_launch_arg "min_telemetry_interval_sec" "${WEB_MAPPING_MIN_TELEMETRY_INTERVAL_SEC:-}"
    add_launch_arg "path_max_points" "${WEB_MAPPING_PATH_MAX_POINTS:-}"
    ;;
  none)
    ;;
  *)
    echo "Unsupported WEB_MAPPING_LAUNCH_ARGS_MODE: ${LAUNCH_ARGS_MODE}" >&2
    exit 1
    ;;
esac

case "${LAUNCH_PACKAGE}/${LAUNCH_FILE}" in
  web_fast_lio_broker/mid360_web_mapping.launch.py)
    add_launch_arg "clean_map_enabled" "${WEB_MAPPING_CLEAN_MAP_ENABLED:-}"
    add_launch_arg "clean_map_voxel_size" "${WEB_MAPPING_CLEAN_MAP_VOXEL_SIZE:-}"
    add_launch_arg "clean_map_min_neighbors" "${WEB_MAPPING_CLEAN_MAP_MIN_NEIGHBORS:-}"
    add_launch_arg "clean_map_radius" "${WEB_MAPPING_CLEAN_MAP_RADIUS:-}"
    add_launch_arg "clean_map_min_z" "${WEB_MAPPING_CLEAN_MAP_MIN_Z:-}"
    add_launch_arg "clean_map_max_z" "${WEB_MAPPING_CLEAN_MAP_MAX_Z:-}"
    add_launch_arg "clean_map_min_retention_ratio" "${WEB_MAPPING_CLEAN_MAP_MIN_RETENTION_RATIO:-}"
    add_launch_arg "clean_map_min_output_points" "${WEB_MAPPING_CLEAN_MAP_MIN_OUTPUT_POINTS:-}"
    ;;
esac

if [[ -n "${WEB_MAPPING_EXTRA_LAUNCH_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  extra_launch_args=(${WEB_MAPPING_EXTRA_LAUNCH_ARGS})
  launch_args+=("${extra_launch_args[@]}")
fi

exec ros2 launch "${LAUNCH_PACKAGE}" "${LAUNCH_FILE}" "${launch_args[@]}"
