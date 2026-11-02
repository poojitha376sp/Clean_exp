#!/usr/bin/env bash
# Run one command on the GPU server, or open a one-shot tunnel to its Ollama. Only needed if you use a
# remote server; with a local GPU skip all of tools/server/ (README: "Running on your own GPU").
# Credentials: GPU_USER / GPU_HOST and GPU_SSH_KEY (or GPU_PASS) in ../.env (see _credentials.sh).
# One shared SSH connection stays open for 4 h so repeated calls are fast.
#   tools/server/gpu_ssh.sh 'nvidia-smi'
#   tools/server/gpu_ssh.sh --tunnel     # localhost:11435 -> server's Ollama (same port as config.yaml)
# For long runs prefer tunnel_keepalive.sh, which reconnects by itself.
# RULE: never run reboot/shutdown/poweroff or sudo through this.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_credentials.sh"
if [[ "${1:-}" =~ (reboot|shutdown|poweroff|halt|sudo) ]]; then
  echo "refused: reboot/shutdown/sudo are not allowed on this server" >&2; exit 1
fi
OPTS=("${SSH_AUTH_OPTS[@]}" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15
      -o ControlMaster=auto -o "ControlPath=/tmp/gpu-ssh-%r@%h" -o ControlPersist=4h)
if [[ "${1:-}" == "--tunnel" ]]; then
  exec setsid ssh "${OPTS[@]}" -N -L 11435:localhost:11434 "$GPU_USER@$GPU_HOST" < /dev/null
fi
setsid ssh "${OPTS[@]}" "$GPU_USER@$GPU_HOST" "$@" < /dev/null
