"""Utility script to query and view pipeline results."""

import argparse
import json
from datetime import datetime

from pymongo import MongoClient

from .config import PipelineConfig


def main():
    """Query and display pipeline results."""
    parser = argparse.ArgumentParser(description="Query pipeline results from MongoDB")

    parser.add_argument(
        "--action",
        choices=[
            "stats",
            "drugs",
            "hierarchy",
            "papers",
            "top-drugs",
            "export-hierarchy",
        ],
        default="stats",
        help="Action to perform",
    )

    parser.add_argument(
        "--limit", type=int, default=20, help="Limit number of results"
    )

    parser.add_argument(
        "--drug-name", type=str, help="Filter by drug name (for 'drugs' action)"
    )

    parser.add_argument(
        "--output", type=str, help="Output file for export actions"
    )

    args = parser.parse_args()

    # Load configuration
    config = PipelineConfig.from_env()

    # Connect to MongoDB
    client = MongoClient(config.mongo_uri)
    db = client[config.mongo_db]

    papers_col = db[config.papers_collection]
    treatments_col = db[config.treatments_collection]
    hierarchy_col = db[config.treatment_hierarchy_collection]

    if args.action == "stats":
        show_statistics(papers_col, treatments_col, hierarchy_col)

    elif args.action == "drugs":
        show_drugs(treatments_col, drug_name=args.drug_name, limit=args.limit)

    elif args.action == "hierarchy":
        show_hierarchy(hierarchy_col)

    elif args.action == "papers":
        show_papers(papers_col, limit=args.limit)

    elif args.action == "top-drugs":
        show_top_drugs(treatments_col, limit=args.limit)

    elif args.action == "export-hierarchy":
        export_hierarchy(hierarchy_col, args.output)

    client.close()


def show_statistics(papers_col, treatments_col, hierarchy_col):
    """Show overall statistics."""
    print("\n" + "=" * 80)
    print("PIPELINE STATISTICS")
    print("=" * 80)

    total_papers = papers_col.count_documents({})
    total_treatments = treatments_col.count_documents({})
    total_hierarchies = hierarchy_col.count_documents({})

    print(f"\nTotal papers in database: {total_papers}")
    print(f"Total treatment records: {total_treatments}")
    print(f"Total hierarchies: {total_hierarchies}")

    if total_treatments > 0:
        # Count unique drugs
        pipeline = [
            {"$unwind": "$treatments"},
            {"$group": {"_id": "$treatments.drug_name"}},
            {"$count": "unique_drugs"},
        ]

        result = list(treatments_col.aggregate(pipeline))
        unique_drugs = result[0]["unique_drugs"] if result else 0

        print(f"Unique drugs found: {unique_drugs}")

        # Most recent hierarchy
        latest = hierarchy_col.find_one({}, sort=[("metadata.generated_at", -1)])

        if latest:
            print(f"\nLatest hierarchy:")
            print(f"  Generated: {latest['metadata']['generated_at']}")
            print(f"  Unique drugs: {latest['metadata']['total_unique_drugs']}")
            print(f"  Drug classes: {latest['metadata']['total_drug_classes']}")
            print(f"  Papers analyzed: {latest['metadata']['total_papers_analyzed']}")

    print()


def show_drugs(treatments_col, drug_name=None, limit=20):
    """Show drug information."""
    print("\n" + "=" * 80)
    print("DRUG INFORMATION")
    print("=" * 80)

    if drug_name:
        # Search for specific drug
        records = treatments_col.find(
            {"treatments.drug_name": {"$regex": drug_name, "$options": "i"}}
        ).limit(limit)

        count = 0
        for record in records:
            count += 1
            print(f"\nPaper: {record.get('paper_title')}")
            print(f"PMID: {record.get('pmid')}")
            print(f"Year: {record.get('paper_year')}")

            for treatment in record.get("treatments", []):
                if drug_name.lower() in treatment.get("drug_name", "").lower():
                    print(f"\n  Drug: {treatment.get('drug_name')}")
                    print(f"  Class: {treatment.get('drug_class')}")
                    print(f"  Target symptoms: {', '.join(treatment.get('target_symptoms', []))}")
                    print(f"  Outcomes: {treatment.get('outcomes')}")

        print(f"\nFound {count} papers mentioning '{drug_name}'")

    else:
        # Show all unique drugs
        pipeline = [
            {"$unwind": "$treatments"},
            {
                "$group": {
                    "_id": "$treatments.drug_name",
                    "count": {"$sum": 1},
                    "classes": {"$addToSet": "$treatments.drug_class"},
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]

        results = list(treatments_col.aggregate(pipeline))

        print(f"\nTop {limit} drugs by paper count:\n")
        for i, drug in enumerate(results, 1):
            classes = [c for c in drug["classes"] if c]
            print(
                f"{i:3}. {drug['_id']:30} - {drug['count']:3} papers - "
                f"Class: {', '.join(classes) if classes else 'N/A'}"
            )

    print()


def show_hierarchy(hierarchy_col):
    """Show treatment hierarchy."""
    print("\n" + "=" * 80)
    print("TREATMENT HIERARCHY")
    print("=" * 80)

    latest = hierarchy_col.find_one({}, sort=[("metadata.generated_at", -1)])

    if not latest:
        print("\nNo hierarchy found.")
        return

    print(f"\nGenerated: {latest['metadata']['generated_at']}")
    print(f"Total unique drugs: {latest['metadata']['total_unique_drugs']}")
    print(f"Total drug classes: {latest['metadata']['total_drug_classes']}")

    # Show primary categories
    print("\n" + "-" * 80)
    print("PRIMARY CATEGORIES")
    print("-" * 80)

    for category, info in latest.get("primary_categories", {}).items():
        print(f"\n{category}:")
        print(f"  {info.get('description')}")
        print(f"  Classes: {', '.join(info.get('drug_classes', []))}")

    # Show drug classes
    print("\n" + "-" * 80)
    print("DRUG CLASSES")
    print("-" * 80)

    for drug_class in latest.get("drug_classes", [])[:10]:  # Show first 10
        print(f"\n{drug_class.get('class_name')} ({drug_class.get('drug_count')} drugs)")
        print(f"  Category: {drug_class.get('primary_category')}")
        print(f"  Purpose: {', '.join(drug_class.get('therapeutic_purpose', []))}")

        # Show top 3 drugs in this class
        for drug in drug_class.get("drugs", [])[:3]:
            print(f"    - {drug.get('drug_name')} ({drug.get('paper_count')} papers)")

    # Show statistics
    stats = latest.get("statistics", {})

    print("\n" + "-" * 80)
    print("TOP STATISTICS")
    print("-" * 80)

    print("\nMost studied drugs:")
    for i, drug in enumerate(stats.get("most_studied_drugs", [])[:10], 1):
        print(f"  {i:2}. {drug['drug']:30} - {drug['paper_count']} papers")

    print("\nMost common symptoms:")
    for i, symptom in enumerate(stats.get("most_common_symptoms", [])[:10], 1):
        print(f"  {i:2}. {symptom['symptom']:30} - {symptom['frequency']} mentions")

    print()


def show_papers(papers_col, limit=20):
    """Show recent papers."""
    print("\n" + "=" * 80)
    print("RECENT PAPERS")
    print("=" * 80)

    papers = papers_col.find({}).sort("stored_at", -1).limit(limit)

    for i, paper in enumerate(papers, 1):
        print(f"\n{i}. {paper.get('title')}")
        print(f"   PMID: {paper.get('pmid')} | Year: {paper.get('year')} | Journal: {paper.get('journal')}")
        print(f"   Authors: {', '.join(paper.get('authors', [])[:3])}")

    print()


def show_top_drugs(treatments_col, limit=20):
    """Show top drugs with detailed information."""
    print("\n" + "=" * 80)
    print(f"TOP {limit} MOST STUDIED DRUGS")
    print("=" * 80)

    pipeline = [
        {"$unwind": "$treatments"},
        {
            "$group": {
                "_id": "$treatments.drug_name",
                "count": {"$sum": 1},
                "classes": {"$addToSet": "$treatments.drug_class"},
                "symptoms": {"$addToSet": "$treatments.target_symptoms"},
                "mechanisms": {"$addToSet": "$treatments.mechanism_of_action"},
            }
        },
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]

    results = list(treatments_col.aggregate(pipeline))

    for i, drug in enumerate(results, 1):
        print(f"\n{i}. {drug['_id']} ({drug['count']} papers)")

        classes = [c for c in drug["classes"] if c]
        if classes:
            print(f"   Classes: {', '.join(classes)}")

        # Flatten and deduplicate symptoms
        all_symptoms = set()
        for symptom_list in drug["symptoms"]:
            if isinstance(symptom_list, list):
                all_symptoms.update(symptom_list)

        if all_symptoms:
            print(f"   Target symptoms: {', '.join(sorted(list(all_symptoms))[:5])}")

        mechanisms = [m for m in drug["mechanisms"] if m]
        if mechanisms:
            print(f"   Mechanisms: {mechanisms[0]}")

    print()


def export_hierarchy(hierarchy_col, output_file):
    """Export hierarchy to JSON file."""
    latest = hierarchy_col.find_one({}, sort=[("metadata.generated_at", -1)])

    if not latest:
        print("No hierarchy found to export.")
        return

    # Remove MongoDB _id field
    latest.pop("_id", None)

    output_file = output_file or f"autism_treatment_hierarchy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, "w") as f:
        json.dump(latest, f, indent=2, default=str)

    print(f"Hierarchy exported to: {output_file}")


if __name__ == "__main__":
    main()
