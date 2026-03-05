"""Checkpoint management for pipeline state persistence."""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from pymongo import MongoClient
from pymongo.collection import Collection

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages pipeline checkpoints for resumability."""

    def __init__(self, mongo_uri: str, db_name: str, collection_name: str):
        """Initialize checkpoint manager.

        Args:
            mongo_uri: MongoDB connection URI
            db_name: Database name
            collection_name: Collection name for checkpoints
        """
        self.client = MongoClient(mongo_uri)
        self.collection: Collection = self.client[db_name][collection_name]

        # Create index on pipeline_id and timestamp
        self.collection.create_index([("pipeline_id", 1), ("timestamp", -1)])

    def save_checkpoint(
        self,
        pipeline_id: str,
        stage: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Save a checkpoint.

        Args:
            pipeline_id: Unique identifier for this pipeline run
            stage: Current stage of the pipeline
            data: Checkpoint data to save
            metadata: Optional metadata about the checkpoint
        """
        checkpoint = {
            "pipeline_id": pipeline_id,
            "stage": stage,
            "timestamp": datetime.utcnow(),
            "data": data,
            "metadata": metadata or {},
        }

        try:
            self.collection.insert_one(checkpoint)
            logger.info(
                f"Checkpoint saved: pipeline_id={pipeline_id}, stage={stage}, "
                f"papers_processed={data.get('papers_processed', 0)}"
            )
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            raise

    def get_latest_checkpoint(
        self, pipeline_id: str, stage: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get the latest checkpoint for a pipeline.

        Args:
            pipeline_id: Pipeline identifier
            stage: Optional stage filter

        Returns:
            Latest checkpoint data or None
        """
        query = {"pipeline_id": pipeline_id}
        if stage:
            query["stage"] = stage

        checkpoint = self.collection.find_one(query, sort=[("timestamp", -1)])

        if checkpoint:
            logger.info(
                f"Loaded checkpoint: pipeline_id={pipeline_id}, "
                f"stage={checkpoint.get('stage')}, "
                f"timestamp={checkpoint.get('timestamp')}"
            )

        return checkpoint

    def delete_pipeline_checkpoints(self, pipeline_id: str) -> int:
        """Delete all checkpoints for a pipeline.

        Args:
            pipeline_id: Pipeline identifier

        Returns:
            Number of checkpoints deleted
        """
        result = self.collection.delete_many({"pipeline_id": pipeline_id})
        logger.info(
            f"Deleted {result.deleted_count} checkpoints for pipeline_id={pipeline_id}"
        )
        return result.deleted_count

    def list_pipelines(self) -> list[str]:
        """List all pipeline IDs with checkpoints.

        Returns:
            List of pipeline IDs
        """
        return self.collection.distinct("pipeline_id")

    def close(self) -> None:
        """Close MongoDB connection."""
        self.client.close()
