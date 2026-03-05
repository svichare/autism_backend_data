"""Runner script for the autism treatment pipeline."""

import argparse
import logging
import sys
from datetime import datetime

from .config import PipelineConfig
from .pipeline import AutismTreatmentPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
    ],
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Autism Pharmacological Treatments Analysis Pipeline"
    )

    parser.add_argument(
        "--max-papers",
        type=int,
        default=None,
        help="Maximum number of papers to process (default: unlimited)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of papers to process per batch (default: 10)",
    )

    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=100,
        help="Save checkpoint every N papers (default: 100)",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint",
    )

    parser.add_argument(
        "--pipeline-id",
        type=str,
        default=None,
        help="Pipeline ID to resume (required if --resume is used)",
    )

    parser.add_argument(
        "--search-term",
        type=str,
        default="autism[Title/Abstract] AND (drug OR medication OR pharmacological OR treatment)",
        help="PubMed search term",
    )

    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="OpenAI model to use (default: gpt-4o-mini)",
    )

    parser.add_argument(
        "--list-pipelines",
        action="store_true",
        help="List all existing pipeline IDs with checkpoints",
    )

    args = parser.parse_args()

    # Load configuration
    config = PipelineConfig.from_env()

    # Override with CLI arguments
    if args.max_papers:
        config.max_total_papers = args.max_papers
    if args.batch_size:
        config.batch_size = args.batch_size
    if args.checkpoint_interval:
        config.checkpoint_interval = args.checkpoint_interval
    if args.search_term:
        config.search_term = args.search_term
    if args.model:
        config.model = args.model

    # Validate configuration
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # List pipelines if requested
    if args.list_pipelines:
        from .checkpoint_manager import CheckpointManager

        checkpoint_manager = CheckpointManager(
            mongo_uri=config.mongo_uri,
            db_name=config.mongo_db,
            collection_name=config.checkpoints_collection,
        )

        pipeline_ids = checkpoint_manager.list_pipelines()

        if pipeline_ids:
            print(f"\nFound {len(pipeline_ids)} pipeline(s):")
            for pid in pipeline_ids:
                checkpoint = checkpoint_manager.get_latest_checkpoint(pid)
                if checkpoint:
                    print(
                        f"  - {pid}: "
                        f"stage={checkpoint.get('stage')}, "
                        f"papers={checkpoint['data'].get('papers_processed', 0)}, "
                        f"timestamp={checkpoint.get('timestamp')}"
                    )
        else:
            print("\nNo pipelines found.")

        checkpoint_manager.close()
        return

    # Validate resume arguments
    if args.resume and not args.pipeline_id:
        logger.error("--pipeline-id is required when using --resume")
        sys.exit(1)

    # Create and run pipeline
    try:
        pipeline = AutismTreatmentPipeline(
            config=config,
            pipeline_id=args.pipeline_id,
        )

        logger.info("=" * 80)
        logger.info("AUTISM TREATMENT PIPELINE")
        logger.info("=" * 80)
        logger.info(f"Pipeline ID: {pipeline.pipeline_id}")
        logger.info(f"Search term: {config.search_term}")
        logger.info(f"Max papers: {config.max_total_papers or 'unlimited'}")
        logger.info(f"Batch size: {config.batch_size}")
        logger.info(f"Checkpoint interval: {config.checkpoint_interval}")
        logger.info(f"Resume: {args.resume}")
        logger.info(f"Model: {config.model}")
        logger.info("=" * 80)

        # Run pipeline
        stats = pipeline.run(resume=args.resume)

        # Print final statistics
        print("\n" + "=" * 80)
        print("PIPELINE RESULTS")
        print("=" * 80)
        print(f"Papers fetched: {stats['papers_fetched']}")
        print(f"Papers with treatments: {stats['papers_with_treatments']}")
        print(f"Total treatments extracted: {stats['total_treatments']}")
        print(f"Errors encountered: {stats['errors']}")

        if stats.get("start_time") and stats.get("end_time"):
            duration = (stats["end_time"] - stats["start_time"]).total_seconds()
            print(f"Duration: {duration:.2f} seconds")

        print("=" * 80)

        # Get database statistics
        db_stats = pipeline.get_statistics()
        print(f"\nDatabase contents:")
        print(f"  Total papers: {db_stats['papers_in_db']}")
        print(f"  Treatment records: {db_stats['treatments_in_db']}")
        print(f"  Hierarchies: {db_stats['hierarchies_in_db']}")
        print()

    except KeyboardInterrupt:
        logger.warning("\nPipeline interrupted by user. Progress has been saved.")
        logger.info(f"To resume, run with: --resume --pipeline-id {pipeline.pipeline_id}")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
