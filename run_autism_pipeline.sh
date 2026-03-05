#!/bin/bash

# Quick start script for the Autism Treatment Pipeline

echo "================================"
echo "Autism Treatment Pipeline"
echo "================================"
echo ""

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Check if dependencies are installed
echo "Checking dependencies..."
python -c "import openai" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing missing dependencies..."
    pip install -r requirements.txt
fi

echo ""
echo "Starting pipeline..."
echo ""

# Run the pipeline with default settings
# Modify these arguments as needed
python -m claude_pipeline.run \
    --max-papers 1000 \
    --batch-size 10 \
    --checkpoint-interval 100 \
    "$@"

echo ""
echo "Pipeline finished!"
