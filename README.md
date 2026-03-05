# pubmed_pipeline

Pipeline to query PubMed Central (PMC), check against internal datasets, and store new results.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
export NCBI_API_KEY=your_api_key_here
pubmed-pipeline --storage local --local-path data/internal.jsonl --email you@example.com
```

You will be prompted for search terms before each run.

## Notes
- NCBI recommends providing an email and optionally an API key for higher rate limits.
- The pipeline supports multiple internal dataset backends: local JSONL, MongoDB Atlas, or DynamoDB.
- Full text is the default. Use `--summary-only` to fetch summaries instead.

## .env support
The CLI loads a local `.env` file (via `python-dotenv`). These environment variables are supported:
- `NCBI_API_KEY`
- `EMAIL_ID`
- `MONGO_URI`
- `MONGO_DB`
- `MONGO_COLLECTION`
- `LOCAL_DATA_PATH`
- `DYNAMODB_TABLE`
- `AWS_REGION`
