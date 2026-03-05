# Quick Start Guide

Get the autism treatment pipeline running in 5 minutes!

## Prerequisites

1. Python 3.8 or higher
2. MongoDB instance (connection details in `.env`)
3. API keys for:
   - NCBI/PubMed
   - OpenAI
   - MongoDB

## Step 1: Install Dependencies

```bash
cd /home/shivaji/svich/always-around.me/code/python/generate_base_data
pip install -r requirements.txt
```

## Step 2: Verify Configuration

Check your `.env` file has all required credentials:

```bash
cat .env
```

Should contain:
- `NCBI_API_KEY`
- `EMAIL_ID`
- `OPENAI_API_KEY`
- `MONGO_URI`
- `MONGO_DB`

## Step 3: Run a Test

Start with a small test run (100 papers):

```bash
python -m claude_pipeline.run --max-papers 100
```

Or use the convenience script:

```bash
./run_autism_pipeline.sh
```

## Step 4: View Results

After the pipeline completes, query the results:

```bash
# View statistics
python -m claude_pipeline.query_results --action stats

# View top drugs
python -m claude_pipeline.query_results --action top-drugs --limit 20

# View hierarchy
python -m claude_pipeline.query_results --action hierarchy

# Export hierarchy to JSON
python -m claude_pipeline.query_results --action export-hierarchy --output my_hierarchy.json
```

## Step 5: Run Full Analysis

For a comprehensive analysis with unlimited papers:

```bash
python -m claude_pipeline.run
```

This will:
1. Fetch ALL autism-related papers from PubMed
2. Extract pharmacological treatments using OpenAI
3. Build a complete hierarchical taxonomy
4. Save checkpoints every 100 papers
5. Store everything in MongoDB

## Common Commands

### Limited Run
```bash
python -m claude_pipeline.run --max-papers 1000
```

### Custom Search Term
```bash
python -m claude_pipeline.run \
  --search-term "autism AND drug therapy" \
  --max-papers 500
```

### Resume from Interruption
```bash
# List existing pipelines
python -m claude_pipeline.run --list-pipelines

# Resume specific pipeline
python -m claude_pipeline.run --resume --pipeline-id autism_pipeline_abc123
```

### Query Specific Drug
```bash
python -m claude_pipeline.query_results --action drugs --drug-name risperidone
```

## What Gets Created

After running, your MongoDB will have 4 collections:

1. **autism_papers** - Raw paper data from PubMed
2. **autism_treatments** - Extracted treatment information
3. **treatment_hierarchy** - Hierarchical classification
4. **pipeline_checkpoints** - Pipeline state for resuming

## Performance Notes

- **Small test** (100 papers): ~5-10 minutes
- **Medium run** (1,000 papers): ~30-60 minutes
- **Large run** (10,000 papers): ~5-8 hours
- **Full dataset** (100,000+ papers): ~2-3 days

The pipeline can be interrupted and resumed at any time!

## Troubleshooting

### API Rate Limits

If you hit rate limits:
- NCBI: The pipeline automatically respects rate limits (~3 req/sec)
- OpenAI: Reduce `--batch-size` or add delays in config

### Out of Memory

Process fewer papers at once:
```bash
python -m claude_pipeline.run --batch-size 5 --max-papers 500
```

### MongoDB Connection Issues

Verify your `MONGO_URI` in `.env` is correct and accessible.

### Resume Not Working

List all pipelines to find the correct ID:
```bash
python -m claude_pipeline.run --list-pipelines
```

## Next Steps

1. Run the pipeline with your desired settings
2. Query and analyze results
3. Export the hierarchy for visualization
4. Customize the search term for specific drugs or conditions

For more details, see [README.md](README.md).
