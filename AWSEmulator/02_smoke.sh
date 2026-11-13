#!/usr/bin/env bash
# Step 2: prove the shell talks to the emulator, not to AWS.
# Run after: source ./env.sh
set -euo pipefail
: "${AWS_ENDPOINT_URL:?Run 'source ./env.sh' first}"

echo "==> Health check"
curl -s --cacert "$AWS_CA_BUNDLE" "$AWS_ENDPOINT_URL/__admin/health"; echo

echo "==> Who am I? (expect account 000000000000)"
python3 - <<'PY'
import boto3, time
t = time.perf_counter()
ident = boto3.client("sts").get_caller_identity()
print(f"Account={ident['Account']}  Arn={ident['Arn']}  ({(time.perf_counter()-t)*1000:.0f} ms)")
s3 = boto3.client("s3")
t = time.perf_counter()
s3.create_bucket(Bucket="hello-emulator")
s3.put_object(Bucket="hello-emulator", Key="hi.txt", Body=b"hello from my laptop")
body = s3.get_object(Bucket="hello-emulator", Key="hi.txt")["Body"].read().decode()
print(f"create bucket + put + get: {(time.perf_counter()-t)*1000:.0f} ms -> {body!r}")
print("Buckets:", [b["Name"] for b in s3.list_buckets()["Buckets"]])
PY

if command -v aws >/dev/null; then
  echo "==> Same thing with the AWS CLI (no --endpoint-url flag needed)"
  aws sts get-caller-identity
  aws s3 ls
fi
