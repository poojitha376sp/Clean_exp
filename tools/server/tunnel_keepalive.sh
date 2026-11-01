#!/usr/bin/env bash
# Self-healing SSH tunnel: localhost:11435 -> rubyserc's Ollama (127.0.0.1:11434).
# Reconnects if the connection drops during a long run. Leave it running in its own terminal.
# 11435 (not 11434) so it cannot clash with a local Ollama; it matches providers.ollama in config.yaml.
source "$(dirname "${BASH_SOURCE[0]}")/_credentials.sh"
while true; do
  setsid ssh -o ControlMaster=no -o ControlPath=none -o ExitOnForwardFailure=yes \
      -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=accept-new \
      -N -L 11435:127.0.0.1:11434 "$GPU_USER@$GPU_HOST" < /dev/null
  echo "$(date +%T) tunnel dropped; reconnecting" >&2
  sleep 5
done
