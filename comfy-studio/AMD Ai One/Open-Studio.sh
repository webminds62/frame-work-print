#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
URL_FILE="$HERE/STUDIO-URL.txt"
URL=""
if [[ -f "$URL_FILE" ]]; then
  URL="$(tr -d '[:space:]' < "$URL_FILE")"
fi
if [[ -z "${URL}" ]]; then
  URL="http://127.0.0.1:42003"
fi

studio_up() {
  curl -fsS --max-time 2 "${URL}/api/health" >/dev/null 2>&1
}

if ! studio_up; then
  PINOKIO_HOME=""
  if [[ -f "${HOME}/.pinokio/config.json" ]]; then
    PINOKIO_HOME="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("home") or "")' "${HOME}/.pinokio/config.json" 2>/dev/null || true)"
  fi
  PTERM=""
  if [[ -n "${PINOKIO_HOME}" && -x "${PINOKIO_HOME}/bin/npm/bin/pterm" ]]; then
    PTERM="${PINOKIO_HOME}/bin/npm/bin/pterm"
  elif command -v pterm >/dev/null 2>&1; then
    PTERM="$(command -v pterm)"
  fi
  if [[ -n "${PTERM}" ]]; then
    (cd "${HERE}/.." && "${PTERM}" start start-studio.js) || true
    for _ in $(seq 1 90); do
      if studio_up; then
        break
      fi
      sleep 2
    done
  fi
fi

if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL"
else
  echo "Open this URL in a browser:"
  echo "$URL"
fi
