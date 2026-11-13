# AWS Emulator demo (MacBook)

Companion code for the article "AWS Just Shipped Its Own Cloud Emulator".
Everything runs on your laptop. No AWS account is used. Scripts refuse to
run if they are not pointed at a local emulator.
Article link - https://arunksingh16.medium.com/aws-just-shipped-its-own-cloud-emulator-heres-how-i-d-wire-it-into-our-devops-98bb1c8050c1?postPublishedType=repub


## Needs
- Docker Desktop (the docs use Docker on macOS; there is no native Mac package)
- Python 3.10+ (uv or venv)
- Optional: AWS CLI v2 (v2.35.0+ if you want the agent skill)

## Troubleshooting first (company network with TLS inspection)
1. Export your Mac keychain CAs once:
   `security find-certificate -a -p /Library/Keychains/System.keychain /System/Library/Keychains/SystemRootCertificates.keychain > ~/mac-ca-bundle.pem`
2. For pip / curl: `export SSL_CERT_FILE=~/mac-ca-bundle.pem REQUESTS_CA_BUNDLE=~/mac-ca-bundle.pem PIP_CERT=~/mac-ca-bundle.pem`
3. `00_build.sh` downloads the RPM with `curl --cacert ~/mac-ca-bundle.pem` on the host and COPYs it into the image, so the build does not need the internet inside Docker. If the base image pull fails, check Docker Desktop > Settings > Proxies, or pull once off the company network.
4. Talking to the emulator itself never goes through the company proxy (it is 127.0.0.1). boto3 trusts the emulator via `AWS_CA_BUNDLE`, which wins over `REQUESTS_CA_BUNDLE`. If you have `HTTPS_PROXY` set, also `export NO_PROXY=127.0.0.1,localhost`.
5. Do not run `env.sh` in a shell where you need real AWS. It unsets your real credentials and replaces `AWS_CONFIG_FILE` for that shell. Open a new terminal tab for real AWS.
6. Container exits with code 137: it went over the 2 GiB cap. State is lost. Restart with `./01_start.sh`.
7. `Address already in use`: run `./99_cleanup.sh`, or pick another port: `./01_start.sh 9300` then `source ./env.sh 9300`.
8. SSL error after a restart: the emulator makes a new certificate and new keys on every start. Re-run `source ./env.sh`.

## Run sheet
```bash
cd demo
uv venv && source .venv/bin/activate      # or python3 -m venv .venv
uv pip install -r requirements.txt         # or pip install -r requirements.txt

./00_build.sh                 # screenshot: version line at the end
./01_start.sh                 # screenshot: "Emulator is up ... after ~Ns"
source ./env.sh
./02_smoke.sh                 # screenshot: account 000000000000 + ms timings
python3 03_probe.py           # screenshot: the service table
./run_tests.sh                # screenshot: 6 passed + API footprint
./run_tests.sh -n 4           # parallel, isolated resources
TEST_BACKEND=moto ./run_tests.sh   # same tests, in-process moto: compare wall time
./05_isolation.sh             # screenshot: two emulators, two worlds
./99_cleanup.sh
```

## Files
| File | What it shows |
|---|---|
| `docker/Dockerfile` | Official Dockerfile, with COPY instead of ADD for TLS-inspected networks |
| `00_build.sh` / `01_start.sh` | Build image (arm64 or x86_64 picked for you), start on 127.0.0.1 only |
| `env.sh` | The env vars from the docs. Your code has no endpoint URL in it |
| `02_smoke.sh` | Health, identity, S3 round trip, timings |
| `03_probe.py` | One read-only call on 24 services: OK / 501 / error |
| `app/orders.py` | Small order service: DynamoDB (idempotent) + S3 + SQS |
| `tests/` | Safety guard, per-test isolation, API footprint recorder |
| `04_footprint.py` / `run_tests.sh` | Which AWS operations your green build depends on |
| `05_isolation.sh` | Per-instance state and keys: the base for parallel CI |
| `ci/github-actions-integration.yml` | moto job + emulator job on Linux, no AWS secrets |
