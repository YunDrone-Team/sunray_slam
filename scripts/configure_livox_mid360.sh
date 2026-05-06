#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUNRAY_SLAM_ROOT="${SUNRAY_SLAM_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"

IFACE="${LIVOX_HOST_IFACE:-eth0}"
TIMEOUT_SEC="${LIVOX_DISCOVERY_TIMEOUT_SEC:-8}"
APPLY="true"
HOST_IP="${LIVOX_HOST_IP:-auto}"
CONFIGS=()
EXTRA_ARGS=()

print_usage() {
  cat <<'USAGE'
Usage: scripts/configure_livox_mid360.sh [options]

Discover a Livox MID360/MID360s on an Ethernet interface and update the bundled
livox_ros_driver2 config files.

Defaults:
  --iface eth0
  --apply
  --host-ip auto
  --config livox_ros_driver2/config/MID360s_config.json
  --config livox_ros_driver2/config/MID360_config.json

Options:
  -i, --iface <name>      Ethernet interface to sniff
  -t, --timeout <sec>     Discovery timeout seconds
  --host-ip <ip|auto>     Host IP to write
  --config <path>         Config file to update; can be repeated
  --dry-run               Discover and print only
  --no-sudo               Do not prefix tcpdump with sudo
  -v, --verbose           Print tcpdump parse diagnostics
  -h, --help              Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -i|--iface)
      IFACE="$2"
      shift 2
      ;;
    -t|--timeout)
      TIMEOUT_SEC="$2"
      shift 2
      ;;
    --host-ip)
      HOST_IP="$2"
      shift 2
      ;;
    --config)
      CONFIGS+=("$2")
      shift 2
      ;;
    --dry-run)
      APPLY="false"
      shift
      ;;
    --apply)
      APPLY="true"
      shift
      ;;
    --no-sudo|--verbose|-v)
      EXTRA_ARGS+=("$1")
      shift
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      print_usage >&2
      exit 2
      ;;
  esac
done

if [[ "${#CONFIGS[@]}" -eq 0 ]]; then
  CONFIGS=(
    "${SUNRAY_SLAM_ROOT}/livox_ros_driver2/config/MID360s_config.json"
    "${SUNRAY_SLAM_ROOT}/livox_ros_driver2/config/MID360_config.json"
  )
fi

args=(
  "${SCRIPT_DIR}/livox_mid360_autoconfig.py"
  --iface "${IFACE}"
  --timeout "${TIMEOUT_SEC}"
  --host-ip "${HOST_IP}"
)

if [[ "${APPLY}" == "true" ]]; then
  args+=(--apply)
fi

for config_path in "${CONFIGS[@]}"; do
  if [[ "${config_path}" != /* ]]; then
    config_path="${SUNRAY_SLAM_ROOT}/${config_path}"
  fi
  args+=(--config "${config_path}")
done

args+=("${EXTRA_ARGS[@]}")

exec /usr/bin/env python3 "${args[@]}"
