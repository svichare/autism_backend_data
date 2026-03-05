"""Main pipeline orchestrator for autism treatment analysis."""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from pymongo import MongoClient
from pymongo.collection import Collection

from .checkpoint_manager import CheckpointManager
from .config import PipelineConfig
from .ncbi_fetcher import NCBIFetcher
from .treatment_classifier import TreatmentClassifier
from .treatment_extractor import TreatmentExtractor

logger = logging.getLogger(__name__)


class AutismTreatmentPipeline:
    """Main pipeline for analyzing autism pharmacological treatments."""

    def __init__(self, config: PipelineConfig, pipeline_id: Optional[str] = None):
        """Initialize pipeline.

        Args:
            config: Pipeline configuration
            pipeline_id: Optional ID for resuming existing pipeline
        """
        self.config = config
        self.pipeline_id = pipeline_id or f"autism_pipeline_{uuid4().hex[:8]}"

        # Initialize components
        self.ncbi_fetcher = NCBIFetcher(
            api_key=config.ncbi_api_key,
            email=config.email,
            rate_limit_delay=config.rate_limit_delay,
        )

        self.treatment_extractor = TreatmentExtractor(
            api_key=config.openai_api_key,
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )

        self.treatment_classifier = TreatmentClassifier(
            api_key=config.openai_api_key,
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )

        # Initialize MongoDB
        self.mongo_client = MongoClient(config.mongo_uri)
        self.db = self.mongo_client[config.mongo_db]

        self.papers_collection: Collection = self.db[config.papers_collection]
        self.treatments_collection: Collection = self.db[config.treatments_collection]
        self.hierarchy_collection: Collection = self.db[
            config.treatment_hierarchy_collection
        ]

        # Create indexes
        self._create_indexes()

        # Checkpoint manager
        self.checkpoint_manager = CheckpointManager(
            mongo_uri=config.mongo_uri,
            db_name=config.mongo_db,
            collection_name=config.checkpoints_collection,
        )

        # State
        self.stats = {
            "papers_fetched": 0,
            "papers_with_treatments": 0,
            "total_treatments": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
        }

    def _create_indexes(self) -> None:
        """Create MongoDB indexes."""
        try:
            self.papers_collection.create_index("pmid", unique=True)
            self.treatments_collection.create_index("pmid")
            self.treatments_collection.create_index("treatments.drug_name")
            self.hierarchy_collection.create_index("metadata.generated_at")
            logger.info("Created MongoDB indexes")
        except Exception as e:
            logger.warning(f"Error creating indexes (may already exist): {e}")

    def run(self, resume: bool = False) -> Dict[str, any]:
        """Run the complete pipeline.

        Args:
            resume: Whether to resume from checkpoint

        Returns:
            Pipeline statistics
        """
        logger.info(f"Starting pipeline: {self.pipeline_id}")
        logger.info(f"Configuration: {self.config}")

        self.stats["start_time"] = datetime.utcnow()

        try:
            # Determine starting point
            start_position = 0
            if resume:
                checkpoint = self.checkpoint_manager.get_latest_checkpoint(
                    self.pipeline_id, stage="fetch_papers"
                )
                if checkpoint:
                    start_position = checkpoint["data"].get("papers_processed", 0)
                    logger.info(f"Resuming from position {start_position}")

            # Stage 1: Fetch and process papers
            logger.info("=" * 80)
            logger.info("STAGE 1: Fetching and analyzing papers")
            logger.info("=" * 80)

            self._fetch_and_analyze_papers(start_from=start_position)

            # Stage 2: Build treatment hierarchy
            logger.info("=" * 80)
            logger.info("STAGE 2: Building treatment hierarchy")
            logger.info("=" * 80)

            self._build_hierarchy()

            # Mark pipeline complete
            self.stats["end_time"] = datetime.utcnow()

            duration = (
                self.stats["end_time"] - self.stats["start_time"]
            ).total_seconds()

            logger.info("=" * 80)
            logger.info("PIPELINE COMPLETE")
            logger.info("=" * 80)
            logger.info(f"Papers fetched: {self.stats['papers_fetched']}")
            logger.info(
                f"Papers with treatments: {self.stats['papers_with_treatments']}"
            )
            logger.info(f"Total treatments extracted: {self.stats['total_treatments']}")
            logger.info(f"Errors encountered: {self.stats['errors']}")
            logger.info(f"Duration: {duration:.2f} seconds")

            # Save final stats
            self.checkpoint_manager.save_checkpoint(
                pipeline_id=self.pipeline_id,
                stage="complete",
                data=self.stats,
                metadata={"config": vars(self.config)},
            )

            return self.stats

        except KeyboardInterrupt:
            logger.warning("Pipeline interrupted by user")
            self.stats["end_time"] = datetime.utcnow()
            self.checkpoint_manager.save_checkpoint(
                pipeline_id=self.pipeline_id,
                stage="interrupted",
                data=self.stats,
            )
            raise

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            self.stats["end_time"] = datetime.utcnow()
            self.stats["error"] = str(e)
            self.checkpoint_manager.save_checkpoint(
                pipeline_id=self.pipeline_id,
                stage="failed",
                data=self.stats,
            )
            raise

        finally:
            self.close()

    def _fetch_and_analyze_papers(self, start_from: int = 0) -> None:
        """Fetch papers and extract treatments.

        Args:
            start_from: Starting position for resuming
        """
        batch_count = 0
        papers_in_batch = []

        # Iterate through papers
        for paper_batch in self.ncbi_fetcher.fetch_papers_iterator(
            term=self.config.search_term,
            max_total=self.config.max_total_papers,
            batch_size=self.config.batch_size,
            start_from=start_from,
        ):
            try:
                # Store raw papers
                self._store_papers(paper_batch)
                self.stats["papers_fetched"] += len(paper_batch)

                # Extract treatments
                treatment_results = self.treatment_extractor.batch_extract_treatments(
                    paper_batch
                )

                if treatment_results:
                    # Add timestamps
                    for result in treatment_results:
                        result["extraction_metadata"]["timestamp"] = (
                            datetime.utcnow().isoformat()
                        )

                    # Store treatments
                    self._store_treatments(treatment_results)

                    self.stats["papers_with_treatments"] += len(treatment_results)

                    # Count total treatments
                    for result in treatment_results:
                        self.stats["total_treatments"] += len(
                            result.get("treatments", [])
                        )

                batch_count += 1
                papers_in_batch.extend(paper_batch)

                # Checkpoint every N batches
                if batch_count % (
                    self.config.checkpoint_interval // self.config.batch_size
                ) == 0:
                    self._save_checkpoint("fetch_papers")
                    logger.info(f"Checkpoint saved at {self.stats['papers_fetched']} papers")

                # Rate limiting for OpenAI
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Error processing batch: {e}", exc_info=True)
                self.stats["errors"] += 1

                # Save error checkpoint
                self._save_checkpoint("fetch_papers_error")

                # Continue with next batch
                continue

        # Final checkpoint for this stage
        self._save_checkpoint("fetch_papers_complete")

    def _store_papers(self, papers: List[Dict[str, any]]) -> None:
        """Store papers in MongoDB.

        Args:
            papers: List of paper dictionaries
        """
        if not papers:
            return

        try:
            # Add timestamp
            for paper in papers:
                paper["stored_at"] = datetime.utcnow()

            # Insert, ignoring duplicates
            self.papers_collection.insert_many(papers, ordered=False)

        except Exception as e:
            # Likely duplicate key errors, which is fine
            logger.debug(f"Some papers already exist in database: {e}")

    def _store_treatments(self, treatment_results: List[Dict[str, any]]) -> None:
        """Store treatment extractions in MongoDB.

        Args:
            treatment_results: List of treatment extraction results
        """
        if not treatment_results:
            return

        try:
            # Add timestamp
            for result in treatment_results:
                result["stored_at"] = datetime.utcnow()

            # Insert, replacing existing
            for result in treatment_results:
                self.treatments_collection.replace_one(
                    {"pmid": result["pmid"]}, result, upsert=True
                )

            logger.info(f"Stored {len(treatment_results)} treatment records")

        except Exception as e:
            logger.error(f"Error storing treatments: {e}")
            raise

    def _build_hierarchy(self) -> None:
        """Build and store treatment hierarchy."""
        try:
            # Fetch all treatment records
            logger.info("Fetching all treatment records from database...")
            treatment_records = list(self.treatments_collection.find({}))

            logger.info(f"Building hierarchy from {len(treatment_records)} records...")

            # Build hierarchy
            hierarchy = self.treatment_classifier.build_treatment_hierarchy(
                treatment_records
            )

            # Store hierarchy
            hierarchy["pipeline_id"] = self.pipeline_id
            hierarchy["stored_at"] = datetime.utcnow()

            self.hierarchy_collection.insert_one(hierarchy)

            logger.info(
                f"Stored treatment hierarchy with "
                f"{hierarchy['metadata']['total_unique_drugs']} unique drugs"
            )

            # Save checkpoint
            self._save_checkpoint(
                "build_hierarchy_complete",
                metadata={"hierarchy_id": str(hierarchy["_id"])},
            )

        except Exception as e:
            logger.error(f"Error building hierarchy: {e}", exc_info=True)
            self.stats["errors"] += 1
            raise

    def _save_checkpoint(
        self, stage: str, metadata: Optional[Dict[str, any]] = None
    ) -> None:
        """Save a checkpoint.

        Args:
            stage: Current stage
            metadata: Optional metadata
        """
        self.checkpoint_manager.save_checkpoint(
            pipeline_id=self.pipeline_id,
            stage=stage,
            data={
                "papers_processed": self.stats["papers_fetched"],
                "papers_with_treatments": self.stats["papers_with_treatments"],
                "total_treatments": self.stats["total_treatments"],
                "errors": self.stats["errors"],
            },
            metadata=metadata,
        )

    def close(self) -> None:
        """Close connections."""
        self.mongo_client.close()
        self.checkpoint_manager.close()

    def get_statistics(self) -> Dict[str, any]:
        """Get current pipeline statistics.

        Returns:
            Statistics dictionary
        """
        return {
            **self.stats,
            "papers_in_db": self.papers_collection.count_documents({}),
            "treatments_in_db": self.treatments_collection.count_documents({}),
            "hierarchies_in_db": self.hierarchy_collection.count_documents({}),
        }
