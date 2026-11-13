#!/usr/bin/env bash
# Step 1: start one emulator in Docker. Usage: ./01_start.sh [port]
# Follows the docs: publish on 127.0.0.1 only, 2 GiB memory cap,
# and mount ~/.aws/emulator so the per-run keys, config and ca.pem
# appear on your Mac under ~/.aws/emulator/<port>/.
set -euo pipefail
PORT="${1:-9297}"
NAME="aws-emu-$PORT"
mkdir -p "$HOME/.aws/emulator"

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --rm --name "$NAME" \
  --memory=2g --memory-swap=2g \
  -p "127.0.0.1:$PORT:$PORT" \
  -e HOME="$HOME" -v "$HOME/.aws/emulator:$HOME/.aws/emulator" \
  ${EMULATOR_TELEMETRY:+-e EMULATOR_TELEMETRY=$EMULATOR_TELEMETRY} \
  aws-emulator -p "$PORT" >/dev/null

echo "==> Waiting for https://127.0.0.1:$PORT/__admin/health"
CA="$HOME/.aws/emulator/$PORT/ca.pem"
for i in $(seq 1 60); do
  if [[ -f "$CA" ]] && curl -fs --cacert "$CA" "https://127.0.0.1:$PORT/__admin/health" >/dev/null 2>&1; then
    echo "Emulator is up on port $PORT after ~${i}s (container: $NAME)"
    echo "Files: $(ls "$HOME/.aws/emulator/$PORT" | tr '\n' ' ')"
    echo "Next: source ./env.sh $PORT"
    exit 0
  fi
  sleep 1
done
echo "Emulator did not become healthy. Logs:"; docker logs "$NAME" | tail -40; exit 1
