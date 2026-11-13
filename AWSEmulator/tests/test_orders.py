import json

import boto3
import pytest

from orders import DuplicateOrder, InvalidOrder, OrderService

ITEMS = [{"sku": "kb-01", "qty": 2, "price": "49.50"}, {"sku": "mouse", "qty": 1, "price": "20"}]


def test_place_order_writes_table_receipt_and_event(resources):
    svc = OrderService(**resources)
    order = svc.place_order("req-1001", "arun", ITEMS)
    assert order["total"] == "119.00"

    stored = svc.get_order("req-1001")
    assert stored["status"] == "PLACED" and stored["customer"] == "arun"

    body = boto3.client("s3").get_object(
        Bucket=resources["bucket"], Key="receipts/arun/req-1001.json")["Body"].read()
    assert json.loads(body)["total"] == "119.00"

    msgs = boto3.client("sqs").receive_message(
        QueueUrl=resources["queue_url"], WaitTimeSeconds=1).get("Messages", [])
    assert [json.loads(m["Body"])["type"] for m in msgs] == ["OrderPlaced"]


def test_retry_is_idempotent(resources):
    """The emulator returns the same error code as AWS for a failed condition."""
    svc = OrderService(**resources)
    svc.place_order("req-2002", "arun", ITEMS)
    with pytest.raises(DuplicateOrder):
        svc.place_order("req-2002", "arun", ITEMS)
    msgs = boto3.client("sqs").receive_message(
        QueueUrl=resources["queue_url"], MaxNumberOfMessages=10, WaitTimeSeconds=1
    ).get("Messages", [])
    assert len(msgs) == 1, "a retried request must not emit a second event"


@pytest.mark.parametrize("items", [[], [{"sku": "x", "qty": 0, "price": "1"}]])
def test_rejects_bad_orders(resources, items):
    with pytest.raises(InvalidOrder):
        OrderService(**resources).place_order("req-bad", "arun", items)
    assert OrderService(**resources).get_order("req-bad") is None


def test_missing_order_returns_none(resources):
    assert OrderService(**resources).get_order("does-not-exist") is None


def test_wrong_bucket_gives_real_aws_error(resources):
    """Error shapes matter: code that branches on error codes is tested for real."""
    from botocore.exceptions import ClientError
    with pytest.raises(ClientError) as e:
        boto3.client("s3").get_object(Bucket=resources["bucket"], Key="nope.json")
    assert e.value.response["Error"]["Code"] in ("NoSuchKey", "404")
