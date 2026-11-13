"""Step 3: what does YOUR emulator version support today?

Calls one cheap, read-only operation on a list of services and prints a
table: OK, NOT IMPLEMENTED (HTTP 501), or another error. Run it after each
emulator upgrade. Run after `source ./env.sh`.
"""
import json
import os
import time
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError

assert os.environ.get("AWS_ENDPOINT_URL", "").startswith("https://127.0.0.1"), \
    "Run `source ./env.sh` first (safety: this script must not hit real AWS)"

PROBES = [
    ("sts", "get_caller_identity", {}),
    ("s3", "list_buckets", {}),
    ("dynamodb", "list_tables", {}),
    ("sqs", "list_queues", {}),
    ("sns", "list_topics", {}),
    ("lambda", "list_functions", {}),
    ("stepfunctions", "list_state_machines", {}),
    ("events", "list_event_buses", {}),
    ("kms", "list_keys", {}),
    ("secretsmanager", "list_secrets", {}),
    ("ssm", "describe_parameters", {}),
    ("iam", "list_roles", {}),
    ("logs", "describe_log_groups", {}),
    ("cloudwatch", "list_metrics", {}),
    ("cloudformation", "list_stacks", {}),
    ("ecr", "describe_repositories", {}),
    ("ecs", "list_clusters", {}),
    ("eks", "list_clusters", {}),
    ("ec2", "describe_vpcs", {}),
    ("rds", "describe_db_instances", {}),
    ("kinesis", "list_streams", {}),
    ("apigateway", "get_rest_apis", {}),
    ("cognito-idp", "list_user_pools", {"MaxResults": 10}),
    ("bedrock", "list_foundation_models", {}),
]

cfg = Config(retries={"max_attempts": 1}, connect_timeout=3, read_timeout=10)
rows = []
print(f"{'service':16} {'operation':26} {'result':22} ms")
print("-" * 72)
for svc, op, kw in PROBES:
    t = time.perf_counter()
    try:
        getattr(boto3.client(svc, config=cfg), op)(**kw)
        result = "OK"
    except ClientError as e:
        code = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        result = "NOT IMPLEMENTED (501)" if code == 501 else f"{e.response['Error'].get('Code')} ({code})"
    except EndpointConnectionError:
        result = "NO ENDPOINT"
    except Exception as e:  # keep probing other services
        result = type(e).__name__
    ms = (time.perf_counter() - t) * 1000
    rows.append({"service": svc, "operation": op, "result": result, "ms": round(ms, 1)})
    print(f"{svc:16} {op:26} {result:22} {ms:5.0f}")

ok = sum(r["result"] == "OK" for r in rows)
print("-" * 72)
print(f"{ok}/{len(rows)} probes OK")
Path("out").mkdir(exist_ok=True)
Path("out/probe.json").write_text(json.dumps(rows, indent=1))
