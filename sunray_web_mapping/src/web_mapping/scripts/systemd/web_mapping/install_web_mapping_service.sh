#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
SERVICE_NAME="${WEB_MAPPING_SERVICE_NAME:-web_mapping.service}"
SERVICE_TEMPLATE="${SCRIPT_DIR}/web_mapping.service.in"
SERVICE_TARGET="/etc/systemd/system/${SERVICE_NAME}"
SERVICE_USER="${WEB_MAPPING_USER:-$(id -un)}"
SERVICE_GROUP="${WEB_MAPPING_GROUP:-$(id -gn "${SERVICE_USER}")}"
SERVICE_HOME="${WEB_MAPPING_HOME:-$(getent passwd "${SERVICE_USER}" | cut -d: -f6)}"
RUNNER_PATH="${WEB_MAPPING_RUNNER:-${SCRIPT_DIR}/run_web_mapping.sh}"
ENV_FILE="${WEB_MAPPING_ENV_FILE:-${SCRIPT_DIR}/web_mapping.env}"

START_SERVICE=1
ENABLE_SERVICE=1

usage() {
  cat <<'USAGE'
Usage: scripts/systemd/web_mapping/install_web_mapping_service.sh [--no-start] [--no-enable]

Install and optionally enable/start web_mapping.service.

Options:
  --no-start    Install and enable the unit, but do not start/restart it now.
  --no-enable   Install the unit without enabling autostart.
  -h, --help    Show this help.
USAGE
}

for arg in "$@"; do
  case "${arg}" in
    --no-start)
      START_SERVICE=0
      ;;
    --no-enable)
      ENABLE_SERVICE=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: ${arg}" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Error: this installer must run on the target Linux device." >&2
  exit 1
fi

if [[ -z "${SERVICE_HOME}" ]]; then
  echo "Error: cannot resolve home directory for user ${SERVICE_USER}." >&2
  exit 1
fi

require_absolute_path() {
  local name="$1"
  local value="$2"
  if [[ "${value}" != /* ]]; then
    echo "Error: ${name} must be an absolute path: ${value}" >&2
    exit 1
  fi
}

escape_sed_replacement() {
  printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'
}

require_absolute_path "WEB_MAPPING_HOME" "${SERVICE_HOME}"
require_absolute_path "WEB_MAPPING_RUNNER" "${RUNNER_PATH}"
require_absolute_path "WEB_MAPPING_ENV_FILE" "${ENV_FILE}"

find_workspace_root() {
  local current="${REPO_ROOT}"
  while [[ "${current}" != "/" ]]; do
    if [[ -f "${current}/install/local_setup.bash" ]] && [[ -d "${current}/src" ]]; then
      printf '%s\n' "${current}"
      return 0
    fi
    current="$(dirname "${current}")"
  done
  return 1
}

WORKSPACE="${WEB_MAPPING_WORKSPACE:-}"
if [[ -z "${WORKSPACE}" ]]; then
  if ! WORKSPACE="$(find_workspace_root)"; then
    WORKSPACE="${REPO_ROOT}"
  fi
fi
require_absolute_path "WEB_MAPPING_WORKSPACE" "${WORKSPACE}"

if [[ ! -f "${WORKSPACE}/install/local_setup.bash" ]]; then
  echo "Error: ${WORKSPACE}/install/local_setup.bash is missing." >&2
  echo "Build first:" >&2
  echo "  cd ${WORKSPACE} && source /opt/ros/<distro>/setup.bash && colcon build --symlink-install" >&2
  exit 1
fi

sudo -v

SERVICE_TMP="$(mktemp)"
sed \
  -e "s/@WEB_MAPPING_USER@/$(escape_sed_replacement "${SERVICE_USER}")/g" \
  -e "s/@WEB_MAPPING_GROUP@/$(escape_sed_replacement "${SERVICE_GROUP}")/g" \
  -e "s/@WEB_MAPPING_HOME@/$(escape_sed_replacement "${SERVICE_HOME}")/g" \
  -e "s/@WEB_MAPPING_WORKSPACE@/$(escape_sed_replacement "${WORKSPACE}")/g" \
  -e "s/@WEB_MAPPING_RUNNER@/$(escape_sed_replacement "${RUNNER_PATH}")/g" \
  -e "s/@WEB_MAPPING_ENV_FILE@/$(escape_sed_replacement "${ENV_FILE}")/g" \
  "${SERVICE_TEMPLATE}" >"${SERVICE_TMP}"
sudo install -m 0644 "${SERVICE_TMP}" "${SERVICE_TARGET}"
rm -f "${SERVICE_TMP}"
sudo systemctl daemon-reload

if ((ENABLE_SERVICE)); then
  sudo systemctl enable "${SERVICE_NAME}"
fi

if ((START_SERVICE)); then
  sudo systemctl restart "${SERVICE_NAME}"
fi

echo "Installed: ${SERVICE_TARGET}"
echo "Workspace: ${WORKSPACE}"
echo "Environment: ${ENV_FILE}"
echo "Autostart: $([[ ${ENABLE_SERVICE} -eq 1 ]] && echo enabled || echo unchanged)"
if ((START_SERVICE)); then
  echo "Started: ${SERVICE_NAME}"
fi
echo "Check status:"
echo "  sudo systemctl status ${SERVICE_NAME}"
echo "  journalctl -u ${SERVICE_NAME} -f"
