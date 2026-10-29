#!/usr/bin/env bash
# Dedicated, self-healing SSH tunnel: localhost:11435 -> rubyserc's Ollama (127.0.0.1:11434).
# Reconnects automatically if the connection drops during long runs.
HERE="$(cd "$(dirname "$0")" && pwd)"
export $(grep -E '^GPU_(USER|HOST|PASS)=' "$HERE/../../.env" | xargs)
ASK="$(mktemp)"; trap 'rm -f "$ASK"' EXIT
printf '#!/bin/sh\nprintf "%%s\\n" "$GPU_PASS"\n' > "$ASK"; chmod 700 "$ASK"
export SSH_ASKPASS="$ASK" SSH_ASKPASS_REQUIRE=force DISPLAY=:0
while true; do
  setsid ssh -o ControlMaster=no -o ControlPath=none -o ExitOnForwardFailure=yes \
      -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=accept-new \
      -N -L 11435:127.0.0.1:11434 "$GPU_USER@$GPU_HOST" < /dev/null
  echo "$(date +%T) tunnel dropped; reconnecting" >&2
  sleep 5
done
