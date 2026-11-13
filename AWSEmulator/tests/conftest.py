"""Test harness. Three ideas a principal engineer would insist on:

1. A safety guard: integration tests refuse to run unless they are pointed at
   a local emulator (127.0.0.1 + account 000000000000). No test should ever
   be one missing env var away from writing to a real account.
2. Per-test isolation: every test creates its own table/bucket/queue with a
   random suffix, so tests can run in parallel (pytest -n 4) and in any order.
3. An API footprint: every AWS call the tests make is recorded
   (service, operation, HTTP status). 04_footprint.py turns it into a report,
   so you can see exactly which AWS behaviour your green build depends on.

Backend is chosen by TEST_BACKEND=emulator (default) or TEST_BACKEND=moto.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
BACKEND = os.environ.get("TEST_BACKEND", "emulator").lower()

if BACKEND == "moto":
    # moto patches botocore in-process. A custom endpoint would bypass it,
    # so drop the emulator settings and use dummy keys.
    for v in ("AWS_ENDPOINT_URL", "AWS_CA_BUNDLE", "AWS_CONFIG_FILE",
              "AWS_SHARED_CREDENTIALS_FILE", "AWS_PROFILE", "AWS_SESSION_TOKEN"):
        os.environ.pop(v, None)
    os.environ.update(AWS_ACCESS_KEY_ID="testing", AWS_SECRET_ACCESS_KEY="testing",
                      AWS_DEFAULT_REGION="us-east-1", AWS_REGION="us-east-1")

import boto3  # noqa: E402  (import after env is fixed)

FOOTPRINT: Counter = Counter()


def _record(http_response=None, model=None, **_):
    if model is None:
        return
    status = getattr(http_response, "status_code", 0)
    FOOTPRINT[(model.service_model.service_name, model.name, status)] += 1


def pytest_report_header(config):
    where = os.environ.get("AWS_ENDPOINT_URL", "in-process mock")
    return f"AWS backend: {BACKEND} ({where})"


@pytest.fixture(scope="session", autouse=True)
def aws_backend():
    if BACKEND == "moto":
        from moto import mock_aws
        with mock_aws():
            boto3.setup_default_session()
            boto3.DEFAULT_SESSION.events.register("after-call", _record)
            yield "moto"
        return

    endpoint = os.environ.get("AWS_ENDPOINT_URL", "")
    if not endpoint.startswith(("https://127.0.0.1", "http://127.0.0.1", "https://localhost")):
        pytest.exit("SAFETY STOP: AWS_ENDPOINT_URL is not a local emulator. "
                    "Run `source ./env.sh` first.", returncode=2)
    boto3.setup_default_session()
    account = boto3.client("sts").get_caller_identity()["Account"]
    if account != "000000000000" and not os.environ.get("ALLOW_NON_EMULATOR_ACCOUNT"):
        pytest.exit(f"SAFETY STOP: account {account} is not the emulator account.", returncode=2)
    boto3.DEFAULT_SESSION.events.register("after-call", _record)
    yield "emulator"


def pytest_sessionfinish(session, exitstatus):
    if not FOOTPRINT:
        return
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    rows = [{"service": s, "operation": o, "status": st, "calls": n}
            for (s, o, st), n in sorted(FOOTPRINT.items())]
    (out / f"footprint-{BACKEND}-{worker}.json").write_text(json.dumps(rows, indent=1))


@pytest.fixture
def resources(aws_backend):
    """Fresh table + bucket + queue for one test, removed afterwards."""
    sfx = uuid.uuid4().hex[:8]
    ddb, s3, sqs = boto3.client("dynamodb"), boto3.client("s3"), boto3.client("sqs")
    table, bucket, queue = f"orders-{sfx}", f"receipts-{sfx}", f"order-events-{sfx}"

    ddb.create_table(
        TableName=table,
        AttributeDefinitions=[{"AttributeName": "order_id", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "order_id", "KeyType": "HASH"}],
        BillingMode="PAY_PER_REQUEST",
    )
    # Real AWS creates tables asynchronously. A good test waits, like prod code.
    ddb.get_waiter("table_exists").wait(TableName=table,
                                        WaiterConfig={"Delay": 1, "MaxAttempts": 30})
    s3.create_bucket(Bucket=bucket)
    queue_url = sqs.create_queue(QueueName=queue)["QueueUrl"]

    yield {"table": table, "bucket": bucket, "queue_url": queue_url}

    for obj in s3.list_objects_v2(Bucket=bucket).get("Contents", []):
        s3.delete_object(Bucket=bucket, Key=obj["Key"])
    s3.delete_bucket(Bucket=bucket)
    sqs.delete_queue(QueueUrl=queue_url)
    ddb.delete_table(TableName=table)
