#!/usr/bin/env bash
set -euo pipefail

workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
livox_source="${LIVOX_ROS_DRIVER2_ROOT:-${workspace_root}/../livox_ros_driver2}"
livox_stage="${workspace_root}/.runtime/external/livox_ros_driver2"

if [[ ! -f "${livox_source}/package_ROS2.xml" ]]; then
  printf 'Missing external Livox ROS 2 driver: %s\n' "${livox_source}" >&2
  printf 'Initialize the sunray_slam submodules before preparing this workspace.\n' >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  printf 'Missing required command: rsync\n' >&2
  exit 1
fi

mkdir -p "${livox_stage}"
rsync -a --delete \
  --exclude='.git' \
  --exclude='build/' \
  --exclude='install/' \
  --exclude='log/' \
  "${livox_source}/" "${livox_stage}/"
cp -f "${livox_stage}/package_ROS2.xml" "${livox_stage}/package.xml"

mkdir -p "${workspace_root}/maps"

echo "Workspace prepared at ${workspace_root}"
echo "Livox ROS 2 driver staged from ${livox_source}"
