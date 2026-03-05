from __future__ import annotations

import argparse
import logging
import os

from dotenv import load_dotenv

from .internal_datasets.dynamodb import DynamoDbDataset
from .internal_datasets.local_files import LocalJsonlDataset
from .internal_datasets.mongo import MongoDataset
from .pipeline import PubMedPipeline


def build_dataset(args: argparse.Namespace):
    if args.storage == "local":
        local_path = args.local_path or os.getenv("LOCAL_DATA_PATH")
        if not local_path:
            raise SystemExit("--local-path is required for local storage")
        return LocalJsonlDataset(local_path)
    if args.storage == "mongodb":
        mongo_uri = args.mongo_uri or os.getenv("MONGO_URI")
        mongo_db = args.mongo_db or os.getenv("MONGO_DB")
        mongo_collection = args.mongo_collection or os.getenv("MONGO_COLLECTION")
        if not mongo_uri or not mongo_db or not mongo_collection:
            raise SystemExit("--mongo-uri, --mongo-db, --mongo-collection are required")
        return MongoDataset(mongo_uri, mongo_db, mongo_collection)
    if args.storage == "dynamodb":
        dynamodb_table = args.dynamodb_table or os.getenv("DYNAMODB_TABLE")
        aws_region = args.aws_region or os.getenv("AWS_REGION")
        if not dynamodb_table:
            raise SystemExit("--dynamodb-table is required")
        return DynamoDbDataset(dynamodb_table, region=aws_region)
    raise SystemExit(f"Unknown storage type: {args.storage}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PubMed Central pipeline")
    parser.add_argument("--storage", choices=["local", "mongodb", "dynamodb"], default="local")
    parser.add_argument("--local-path")
    parser.add_argument("--mongo-uri")
    parser.add_argument("--mongo-db")
    parser.add_argument("--mongo-collection")
    parser.add_argument("--aws-region")
    parser.add_argument("--dynamodb-table")

    parser.add_argument("--email")
    parser.add_argument("--api-key")

    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--requests-per-second", type=float, default=3.0)
    parser.add_argument("--log-level", default="INFO", help="DEBUG, INFO, WARNING, ERROR")
    parser.add_argument("--summary-only", action="store_true", help="Fetch PMC summaries instead of full text")

    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    email = args.email or os.getenv("EMAIL_ID")
    if not email:
        raise SystemExit("--email or EMAIL_ID is required")
    dataset = build_dataset(args)
    api_key = args.api_key or os.getenv("NCBI_API_KEY")
    pipeline = PubMedPipeline(
        dataset,
        email=email,
        api_key=api_key,
        max_results=args.max_results,
        requests_per_second=args.requests_per_second,
        full_text=not args.summary_only,
    )

    term = input("Enter search terms: ").strip()
    if not term:
        raise SystemExit("No search terms provided")

    stats = pipeline.run(term)
    print("Done", stats)


if __name__ == "__main__":
    main()
