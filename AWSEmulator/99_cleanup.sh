#!/usr/bin/env bash
# Stop all demo emulators. State is in memory, so stopping deletes it.
for c in $(docker ps --format '{{.Names}}' | grep '^aws-emu-' || true); do docker rm -f "$c"; done
echo "Stopped. Optional: docker image rm aws-emulator && rm -rf ~/.aws/emulator"
