"""A small, realistic service: place an order.

It writes the order to DynamoDB (idempotent on request_id), stores a JSON
receipt in S3, and queues an event on SQS for the fulfilment team.

Note what is NOT here: no endpoint URL, no credentials, no "if local:"
branch. The same code runs against AWS, the AWS Emulator, or moto. The
environment decides.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError


class DuplicateOrder(Exception):
    pass


class InvalidOrder(ValueError):
    pass


@dataclass
class OrderService:
    table: str
    bucket: str
    queue_url: str

    def __post_init__(self):
        self.ddb = boto3.client("dynamodb")
        self.s3 = boto3.client("s3")
        self.sqs = boto3.client("sqs")

    def place_order(self, request_id: str, customer: str, items: list[dict]) -> dict:
        if not items:
            raise InvalidOrder("an order needs at least one item")
        for it in items:
            if it.get("qty", 0) <= 0 or Decimal(str(it.get("price", 0))) < 0:
                raise InvalidOrder(f"bad item: {it}")
        total = sum(Decimal(str(i["price"])) * i["qty"] for i in items)
        order = {
            "order_id": request_id,
            "customer": customer,
            "total": str(total),
            "items": items,
            "created_at": int(time.time()),
        }
        try:
            self.ddb.put_item(
                TableName=self.table,
                Item={
                    "order_id": {"S": request_id},
                    "customer": {"S": customer},
                    "total": {"N": str(total)},
                    "status": {"S": "PLACED"},
                },
                # Idempotency: a retried request must not create a second order.
                ConditionExpression="attribute_not_exists(order_id)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise DuplicateOrder(request_id) from e
            raise
        self.s3.put_object(
            Bucket=self.bucket,
            Key=f"receipts/{customer}/{request_id}.json",
            Body=json.dumps(order).encode(),
            ContentType="application/json",
        )
        self.sqs.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps({"type": "OrderPlaced", "order_id": request_id}),
        )
        return order

    def get_order(self, order_id: str) -> dict | None:
        r = self.ddb.get_item(TableName=self.table, Key={"order_id": {"S": order_id}},
                              ConsistentRead=True)
        item = r.get("Item")
        if not item:
            return None
        return {k: list(v.values())[0] for k, v in item.items()}
