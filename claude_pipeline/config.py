"""Configuration management for the autism treatment pipeline."""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class PipelineConfig:
    """Configuration for the autism treatment pipeline."""

    # Required fields (no defaults)
    ncbi_api_key: str
    email: str
    openai_api_key: str
    mongo_uri: str
    mongo_db: str

    # NCBI/PubMed configuration
    search_term: str = "autism"
    max_papers_per_batch: int = 100
    max_total_papers: Optional[int] = None  # None means unlimited

    # OpenAI configuration
    model: str = "gpt-4o-mini"
    max_tokens: int = 4000
    temperature: float = 0.1

    # Collection names
    papers_collection: str = "autism_papers"
    treatments_collection: str = "autism_treatments"
    treatment_hierarchy_collection: str = "treatment_hierarchy"
    checkpoints_collection: str = "pipeline_checkpoints"

    # Pipeline settings
    checkpoint_interval: int = 100
    retry_attempts: int = 3
    retry_delay: int = 5
    batch_size: int = 10
    rate_limit_delay: float = 0.34  # ~3 requests per second for NCBI

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        """Create configuration from environment variables."""
        return cls(
            ncbi_api_key=os.getenv("NCBI_API_KEY", ""),
            email=os.getenv("EMAIL_ID", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            mongo_uri=os.getenv("MONGO_URI", ""),
            mongo_db=os.getenv("MONGO_DB", "autism_research"),
        )

    def validate(self) -> None:
        """Validate that all required configuration is present."""
        errors = []

        if not self.ncbi_api_key:
            errors.append("NCBI_API_KEY is required")
        if not self.email:
            errors.append("EMAIL_ID is required")
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY is required")
        if not self.mongo_uri:
            errors.append("MONGO_URI is required")

        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
