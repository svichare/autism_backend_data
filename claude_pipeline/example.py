"""Example usage of the autism treatment pipeline."""

import logging

from .config import PipelineConfig
from .pipeline import AutismTreatmentPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def example_full_run():
    """Example: Run a full pipeline analysis."""
    print("\n" + "=" * 80)
    print("EXAMPLE: Full Pipeline Run")
    print("=" * 80)

    # Create configuration from environment
    config = PipelineConfig.from_env()

    # Customize settings
    config.max_total_papers = 100  # Limit to 100 papers for example
    config.batch_size = 10
    config.checkpoint_interval = 50

    # Validate configuration
    config.validate()

    # Create and run pipeline
    pipeline = AutismTreatmentPipeline(config=config)

    print(f"\nPipeline ID: {pipeline.pipeline_id}")
    print(f"Will process up to {config.max_total_papers} papers")
    print("Starting pipeline...\n")

    # Run the pipeline
    stats = pipeline.run(resume=False)

    # Print results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Papers fetched: {stats['papers_fetched']}")
    print(f"Papers with treatments: {stats['papers_with_treatments']}")
    print(f"Total treatments extracted: {stats['total_treatments']}")
    print(f"Errors: {stats['errors']}")

    if stats.get("start_time") and stats.get("end_time"):
        duration = (stats["end_time"] - stats["start_time"]).total_seconds()
        print(f"Duration: {duration:.2f} seconds")

    print("\nTo view results, run:")
    print(f"  python -m claude_pipeline.query_results --action stats")
    print(f"  python -m claude_pipeline.query_results --action top-drugs")
    print(f"  python -m claude_pipeline.query_results --action hierarchy")


def example_resume():
    """Example: Resume from a checkpoint."""
    print("\n" + "=" * 80)
    print("EXAMPLE: Resume from Checkpoint")
    print("=" * 80)

    config = PipelineConfig.from_env()
    config.validate()

    # Specify the pipeline ID to resume
    pipeline_id = "autism_pipeline_abc123"  # Replace with actual ID

    pipeline = AutismTreatmentPipeline(config=config, pipeline_id=pipeline_id)

    print(f"\nResuming pipeline: {pipeline_id}")

    # Run with resume=True
    stats = pipeline.run(resume=True)

    print(f"\nPipeline resumed and completed!")


def example_query_results():
    """Example: Query results from database."""
    print("\n" + "=" * 80)
    print("EXAMPLE: Query Results")
    print("=" * 80)

    from pymongo import MongoClient

    config = PipelineConfig.from_env()
    client = MongoClient(config.mongo_uri)
    db = client[config.mongo_db]

    # Query papers
    print("\nQuerying papers...")
    papers_col = db[config.papers_collection]
    paper_count = papers_col.count_documents({})
    print(f"Total papers in database: {paper_count}")

    # Query treatments
    print("\nQuerying treatments...")
    treatments_col = db[config.treatments_collection]
    treatment_count = treatments_col.count_documents({})
    print(f"Total treatment records: {treatment_count}")

    # Find most common drug
    pipeline = [
        {"$unwind": "$treatments"},
        {"$group": {"_id": "$treatments.drug_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]

    print("\nTop 5 most studied drugs:")
    for i, result in enumerate(treatments_col.aggregate(pipeline), 1):
        print(f"  {i}. {result['_id']}: {result['count']} papers")

    # Query hierarchy
    print("\nQuerying hierarchy...")
    hierarchy_col = db[config.treatment_hierarchy_collection]
    latest_hierarchy = hierarchy_col.find_one({}, sort=[("metadata.generated_at", -1)])

    if latest_hierarchy:
        print(f"Latest hierarchy generated: {latest_hierarchy['metadata']['generated_at']}")
        print(f"  Unique drugs: {latest_hierarchy['metadata']['total_unique_drugs']}")
        print(f"  Drug classes: {latest_hierarchy['metadata']['total_drug_classes']}")
    else:
        print("No hierarchy found yet.")

    client.close()


def example_custom_search():
    """Example: Custom search term."""
    print("\n" + "=" * 80)
    print("EXAMPLE: Custom Search Term")
    print("=" * 80)

    config = PipelineConfig.from_env()

    # Use a more specific search term
    config.search_term = (
        "autism[Title/Abstract] AND (risperidone OR aripiprazole) AND treatment"
    )
    config.max_total_papers = 50

    config.validate()

    pipeline = AutismTreatmentPipeline(config=config)

    print(f"\nSearch term: {config.search_term}")
    print(f"Max papers: {config.max_total_papers}")
    print("\nStarting pipeline...\n")

    stats = pipeline.run()

    print(f"\nCompleted! Found {stats['papers_with_treatments']} papers with treatments")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        example = sys.argv[1]

        if example == "full":
            example_full_run()
        elif example == "resume":
            example_resume()
        elif example == "query":
            example_query_results()
        elif example == "custom":
            example_custom_search()
        else:
            print(f"Unknown example: {example}")
            print("Available examples: full, resume, query, custom")
    else:
        print("Usage: python -m claude_pipeline.example <example_name>")
        print("\nAvailable examples:")
        print("  full    - Run a full pipeline with 100 papers")
        print("  resume  - Resume from a checkpoint")
        print("  query   - Query results from database")
        print("  custom  - Use a custom search term")
