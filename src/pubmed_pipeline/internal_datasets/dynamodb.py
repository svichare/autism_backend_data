from __future__ import annotations

from typing import Dict, Iterable

import boto3
from botocore.exceptions import ClientError

from .base import InternalDataset


class DynamoDbDataset(InternalDataset):
    def __init__(self, table_name: str, region: str | None = None) -> None:
        self.resource = boto3.resource("dynamodb", region_name=region)
        self.table = self.resource.Table(table_name)

    def exists(self, paper_id: str) -> bool:
        try:
            response = self.table.get_item(Key={"paper_id": str(paper_id)})
        except ClientError:
            return False
        return "Item" in response

    def add_many(self, papers: Iterable[Dict]) -> None:
        with self.table.batch_writer(overwrite_by_pkeys=["paper_id"]) as batch:
            for paper in papers:
                paper_id = paper.get("paper_id")
                if not paper_id:
                    continue
                item = dict(paper)
                item["paper_id"] = str(paper_id)
                batch.put_item(Item=item)
