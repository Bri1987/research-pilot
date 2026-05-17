#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_FILE="${PROJECT_ROOT}/data/outputs/researchpilot_streamlit.pid"
PORT="${RESEARCHPILOT_PORT:-8501}"
stopped=0

stop_pid() {
  local pid="$1"
  if [[ -z "${pid}" ]]; then
    return 0
  fi
  if ! kill -0 "${pid}" 2>/dev/null; then
    return 0
  fi

  kill "${pid}" 2>/dev/null || true
  for _ in {1..30}; do
    if ! kill -0 "${pid}" 2>/dev/null; then
      echo "Stopped ResearchPilot process ${pid}."
      stopped=1
      return 0
    fi
    sleep 0.2
  done

  echo "Process ${pid} did not stop after SIGTERM; sending SIGKILL." >&2
  kill -9 "${pid}" 2>/dev/null || true
  stopped=1
}

if [[ -f "${PID_FILE}" ]]; then
  pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
  stop_pid "${pid}"
  rm -f "${PID_FILE}"
fi

if command -v lsof >/dev/null 2>&1 && command -v ps >/dev/null 2>&1; then
  while IFS= read -r pid; do
    [[ -z "${pid}" ]] && continue
    command_line="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
    if [[ "${command_line}" == *"streamlit"* && "${command_line}" == *"app/streamlit_app.py"* ]]; then
      stop_pid "${pid}"
    fi
  done < <(lsof -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || true)
fi

rm -f "${PID_FILE}"

if [[ "${stopped}" -eq 0 ]]; then
  echo "ResearchPilot is not running."
else
  echo "ResearchPilot stopped."
fi
