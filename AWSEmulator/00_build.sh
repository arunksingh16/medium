#!/usr/bin/env bash
# Step 0: download the AWS Emulator RPM and build a local Docker image.
# macOS has no native package, so the docs use Docker on Mac.
set -euo pipefail
cd "$(dirname "$0")/docker"

case "$(uname -m)" in
  arm64|aarch64) ARCH=aarch64 ;;   # Apple silicon
  *)             ARCH=x86_64 ;;
esac
URL="https://downloads.aws.com/aws-emulator/packages/aws-emulator/LTS/latest/aws-emulator-${ARCH}.rpm"

# Company network with TLS inspection? Use your exported keychain bundle.
CURL_CA=()
if [[ -f "${CORP_CA_BUNDLE:-$HOME/mac-ca-bundle.pem}" ]]; then
  CURL_CA=(--cacert "${CORP_CA_BUNDLE:-$HOME/mac-ca-bundle.pem}")
fi

echo "==> Downloading $URL"
curl -fSL ${CURL_CA[@]+"${CURL_CA[@]}"} -o aws-emulator.rpm "$URL"

echo "==> Building image 'aws-emulator' for $ARCH"
docker build -t aws-emulator .

echo "==> Emulator version inside the image:"
docker run --rm --entrypoint aws-emulator aws-emulator -v || true

mkdir -p "$HOME/.aws/emulator"
echo "Done. Next: ./01_start.sh"
