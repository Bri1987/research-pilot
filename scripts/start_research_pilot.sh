#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_FILE="${PROJECT_ROOT}/data/outputs/researchpilot_streamlit.pid"
LOG_FILE="${PROJECT_ROOT}/data/outputs/researchpilot_streamlit.log"
HOME_DIR="${PROJECT_ROOT}/.streamlit-home"
HOST="${RESEARCHPILOT_HOST:-127.0.0.1}"
PORT="${RESEARCHPILOT_PORT:-8501}"

mkdir -p "$(dirname "${PID_FILE}")" "${HOME_DIR}"

if [[ -f "${PID_FILE}" ]]; then
  existing_pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${existing_pid}" ]] && kill -0 "${existing_pid}" 2>/dev/null; then
    echo "ResearchPilot is already running: http://${HOST}:${PORT} (pid ${existing_pid})"
    exit 0
  fi
  rm -f "${PID_FILE}"
fi

if command -v lsof >/dev/null 2>&1; then
  if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port ${PORT} is already in use. Set RESEARCHPILOT_PORT or stop the existing service first." >&2
    exit 1
  fi
fi

if [[ -x "${PROJECT_ROOT}/.venv/bin/streamlit" ]]; then
  STREAMLIT_BIN="${PROJECT_ROOT}/.venv/bin/streamlit"
else
  STREAMLIT_BIN="$(command -v streamlit)"
fi

cd "${PROJECT_ROOT}"
(
  HOME="${HOME_DIR}" \
  STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
  "${STREAMLIT_BIN}" run app/streamlit_app.py \
    --server.fileWatcherType none \
    --server.address "${HOST}" \
    --server.port "${PORT}" \
    --server.headless true
) >"${LOG_FILE}" 2>&1 &

pid="$!"
echo "${pid}" >"${PID_FILE}"
echo "ResearchPilot started: http://${HOST}:${PORT}"
echo "PID: ${pid}"
echo "Log: ${LOG_FILE}"
