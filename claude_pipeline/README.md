# Autism Pharmacological Treatments Analysis Pipeline

A comprehensive Python pipeline that fetches research papers about autism from NCBI/PubMed, extracts pharmacological treatments using LLM analysis, and builds a hierarchical classification of all treatments tried for autism.

## Features

- **Scalable**: Can process millions of papers with proper checkpointing
- **Resilient**: Error handling with automatic retries and checkpoint recovery
- **Comprehensive**: Extracts detailed treatment information including drug names, classes, mechanisms, dosages, and outcomes
- **Hierarchical**: Builds a complete taxonomy of autism treatments organized by drug class and therapeutic purpose
- **Resumable**: Can resume from checkpoints if interrupted

## Architecture

The pipeline consists of several modules:

1. **NCBIFetcher** (`ncbi_fetcher.py`): Fetches papers from PubMed with pagination and rate limiting
2. **TreatmentExtractor** (`treatment_extractor.py`): Uses OpenAI GPT to extract pharmacological interventions from papers
3. **TreatmentClassifier** (`treatment_classifier.py`): Organizes treatments into hierarchical structure
4. **CheckpointManager** (`checkpoint_manager.py`): Manages pipeline state for resumability
5. **Pipeline** (`pipeline.py`): Main orchestrator that coordinates all components

## MongoDB Schema

### Collections

#### 1. `autism_papers`
Stores raw paper data from PubMed:
```json
{
  "pmid": "12345678",
  "title": "Paper title",
  "abstract": "Paper abstract...",
  "authors": ["Author 1", "Author 2"],
  "journal": "Journal name",
  "year": "2023",
  "keywords": ["autism", "treatment"],
  "source": "pubmed",
  "stored_at": "2024-01-01T00:00:00"
}
```

#### 2. `autism_treatments`
Stores extracted treatment information:
```json
{
  "pmid": "12345678",
  "paper_title": "Paper title",
  "paper_authors": ["Author 1"],
  "paper_journal": "Journal name",
  "paper_year": "2023",
  "has_pharmacological_treatment": true,
  "treatments": [
    {
      "drug_name": "Risperidone",
      "alternative_names": ["Risperdal"],
      "drug_class": "Atypical Antipsychotic",
      "mechanism_of_action": "D2 receptor antagonist",
      "dosage": "0.5-3.5 mg/day",
      "target_symptoms": ["irritability", "aggression"],
      "outcomes": "Significant reduction in irritability",
      "adverse_effects": ["weight gain", "sedation"],
      "study_type": "RCT"
    }
  ],
  "notes": "Additional notes",
  "extraction_metadata": {
    "model": "gpt-4o-mini",
    "timestamp": "2024-01-01T00:00:00"
  },
  "stored_at": "2024-01-01T00:00:00"
}
```

#### 3. `treatment_hierarchy`
Stores hierarchical classification of all treatments:
```json
{
  "pipeline_id": "autism_pipeline_abc123",
  "drug_classes": [
    {
      "primary_category": "Psychotropic Medications",
      "secondary_category": "Antipsychotics",
      "class_name": "Atypical Antipsychotic",
      "therapeutic_purpose": ["Behavioral symptoms", "Irritability"],
      "description": "Second-generation antipsychotics",
      "drug_count": 5,
      "drugs": [
        {
          "drug_name": "Risperidone",
          "alternative_names": ["Risperdal"],
          "mechanisms": ["D2 receptor antagonist"],
          "target_symptoms": ["irritability", "aggression"],
          "paper_count": 45,
          "study_types": ["RCT", "observational"]
        }
      ]
    }
  ],
  "primary_categories": {
    "Psychotropic Medications": {
      "description": "Medications affecting mental state",
      "drug_classes": ["Atypical Antipsychotic", "SSRI", "Stimulant"]
    }
  },
  "statistics": {
    "most_studied_drugs": [
      {"drug": "risperidone", "paper_count": 45}
    ],
    "most_common_symptoms": [
      {"symptom": "irritability", "frequency": 120}
    ],
    "study_type_distribution": {
      "RCT": 150,
      "observational": 80
    }
  },
  "metadata": {
    "total_papers_analyzed": 500,
    "total_unique_drugs": 85,
    "total_drug_classes": 15,
    "generated_at": "2024-01-01T00:00:00"
  },
  "stored_at": "2024-01-01T00:00:00"
}
```

#### 4. `pipeline_checkpoints`
Stores pipeline state for resumability:
```json
{
  "pipeline_id": "autism_pipeline_abc123",
  "stage": "fetch_papers",
  "timestamp": "2024-01-01T00:00:00",
  "data": {
    "papers_processed": 1000,
    "papers_with_treatments": 450,
    "total_treatments": 1200,
    "errors": 5
  },
  "metadata": {}
}
```

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables in `.env`:
```bash
NCBI_API_KEY=your_ncbi_api_key
EMAIL_ID=your_email@example.com
OPENAI_API_KEY=your_openai_api_key
MONGO_URI=your_mongodb_uri
MONGO_DB=autism_research
```

## Usage

### Basic Usage

Run the pipeline with default settings (will process all available papers):
```bash
python -m claude_pipeline.run
```

### Limited Run

Process a specific number of papers:
```bash
python -m claude_pipeline.run --max-papers 1000
```

### Custom Search

Use a custom PubMed search term:
```bash
python -m claude_pipeline.run \
  --search-term "autism[Title/Abstract] AND (pharmacological intervention)" \
  --max-papers 500
```

### Resuming from Checkpoint

If the pipeline is interrupted, resume from the last checkpoint:
```bash
# First, list existing pipelines
python -m claude_pipeline.run --list-pipelines

# Then resume a specific pipeline
python -m claude_pipeline.run --resume --pipeline-id autism_pipeline_abc123
```

### Advanced Options

```bash
python -m claude_pipeline.run \
  --max-papers 10000 \
  --batch-size 20 \
  --checkpoint-interval 200 \
  --model gpt-4o \
  --search-term "autism AND drug therapy"
```

### Command Line Arguments

- `--max-papers N`: Maximum number of papers to process (default: unlimited)
- `--batch-size N`: Papers to process per batch (default: 10)
- `--checkpoint-interval N`: Save checkpoint every N papers (default: 100)
- `--resume`: Resume from last checkpoint
- `--pipeline-id ID`: Pipeline ID to resume
- `--search-term TERM`: PubMed search term
- `--model MODEL`: OpenAI model (default: gpt-4o-mini)
- `--list-pipelines`: List all existing pipeline runs

## Pipeline Stages

### Stage 1: Fetch and Analyze Papers

1. Searches PubMed for papers matching the search term
2. Fetches detailed paper information (title, abstract, authors, etc.)
3. Stores papers in MongoDB
4. Analyzes each paper with OpenAI to extract pharmacological treatments
5. Stores treatment extractions in MongoDB
6. Creates checkpoints every 100 papers

### Stage 2: Build Treatment Hierarchy

1. Retrieves all treatment records from MongoDB
2. Aggregates information about unique drugs
3. Groups drugs by class
4. Uses OpenAI to create hierarchical classification
5. Calculates statistics (most studied drugs, common symptoms, etc.)
6. Stores final hierarchy in MongoDB

## Error Handling

- **NCBI rate limiting**: Automatic delays between requests (~3 req/sec)
- **OpenAI API errors**: 3 retry attempts with exponential backoff
- **Network errors**: Batch-level error handling, continues with next batch
- **Checkpoint recovery**: Can resume from any checkpoint after interruption

## Checkpointing

The pipeline saves checkpoints:
- Every 100 papers processed (configurable)
- After each stage completion
- On errors or interruptions

Checkpoints include:
- Number of papers processed
- Number of treatments extracted
- Error count
- Current pipeline stage

## Performance Considerations

- **NCBI API**: ~3 requests per second (respects rate limits)
- **OpenAI API**: Processes papers in batches of 10 (configurable)
- **MongoDB**: Batch inserts for efficiency
- **Memory**: Processes papers in batches to avoid memory issues
- **Scalability**: Can handle millions of papers with checkpointing

## Example Output

After running the pipeline, you'll have:

1. A comprehensive database of autism research papers
2. Detailed extraction of all pharmacological treatments mentioned
3. A hierarchical taxonomy of treatments organized by:
   - Primary category (e.g., "Psychotropic Medications", "Supplements")
   - Drug class (e.g., "SSRIs", "Antipsychotics", "Stimulants")
   - Individual drugs with all mentions aggregated

4. Statistics including:
   - Most studied drugs
   - Most commonly targeted symptoms
   - Distribution of study types

## Logging

Logs are written to:
- Console (INFO level)
- File: `pipeline_YYYYMMDD_HHMMSS.log` (all levels)

## License

This pipeline is for research purposes.
