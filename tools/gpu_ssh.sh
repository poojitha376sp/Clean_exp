#!/usr/bin/env bash
# Run one command on the SERC GPU server (rubyserc). Credentials come from
# Honours-Testing/.env (GPU_USER / GPU_HOST / GPU_PASS). Keeps one shared SSH
# connection open for 4h so repeated calls are fast.
#   tools/gpu_ssh.sh 'nvidia-smi'
#   tools/gpu_ssh.sh --tunnel      # forward localhost:11434 -> server's Ollama
# RULE: never run reboot/shutdown/poweroff or sudo through this.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$HERE/../../.env"
export $(grep -E '^GPU_(USER|HOST|PASS)=' "$ENV_FILE" | xargs)
if [[ "${1:-}" =~ (reboot|shutdown|poweroff|halt|sudo) ]]; then
  echo "refused: reboot/shutdown/sudo are not allowed on this server" >&2; exit 1
fi
ASK="$(mktemp)"; trap 'rm -f "$ASK"' EXIT
printf '#!/bin/sh\nprintf "%%s\\n" "$GPU_PASS"\n' > "$ASK"; chmod 700 "$ASK"
OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15
      -o ControlMaster=auto -o "ControlPath=/tmp/gpu-ssh-%r@%h" -o ControlPersist=4h)
export SSH_ASKPASS="$ASK" SSH_ASKPASS_REQUIRE=force DISPLAY=:0
if [[ "${1:-}" == "--tunnel" ]]; then
  exec setsid ssh "${OPTS[@]}" -N -L 11434:localhost:11434 "$GPU_USER@$GPU_HOST" < /dev/null
fi
setsid ssh "${OPTS[@]}" "$GPU_USER@$GPU_HOST" "$@" < /dev/null
