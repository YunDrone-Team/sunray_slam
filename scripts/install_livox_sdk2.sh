#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/sunray_env.sh"

BUILD_DIR="${BUILD_DIR:-${LIVOX_SDK2_ROOT}/build}"

log() {
  printf '[livox-sdk2] %s\n' "$*"
}

if [[ ! -d "${LIVOX_SDK2_ROOT}" ]]; then
  printf '[livox-sdk2] missing SDK source: %s\n' "${LIVOX_SDK2_ROOT}" >&2
  printf '[livox-sdk2] run: git submodule update --init --recursive\n' >&2
  exit 1
fi

if [[ ! -f "${LIVOX_SDK2_ROOT}/CMakeLists.txt" ]]; then
  printf '[livox-sdk2] missing CMakeLists.txt in: %s\n' "${LIVOX_SDK2_ROOT}" >&2
  exit 1
fi

mkdir -p "${BUILD_DIR}"

log "source: ${LIVOX_SDK2_ROOT}"
log "build: ${BUILD_DIR}"

cmake -S "${LIVOX_SDK2_ROOT}" -B "${BUILD_DIR}"
cmake --build "${BUILD_DIR}" --parallel "$(nproc)"
sudo cmake --install "${BUILD_DIR}"
sudo ldconfig

log "installed Livox-SDK2 to the system library path"
