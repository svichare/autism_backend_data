"""Extract pharmacological treatments from research papers using LLM."""

import json
import logging
from typing import Dict, List, Optional

import openai

logger = logging.getLogger(__name__)


class TreatmentExtractor:
    """Extracts autism pharmacological treatments from papers using LLM."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 4000,
        temperature: float = 0.1,
    ):
        """Initialize treatment extractor.

        Args:
            api_key: OpenAI API key
            model: OpenAI model to use
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
        """
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def extract_treatments(
        self, paper: Dict[str, any], retry_attempts: int = 3
    ) -> Optional[Dict[str, any]]:
        """Extract pharmacological treatments from a paper.

        Args:
            paper: Paper dictionary with title, abstract, etc.
            retry_attempts: Number of retry attempts

        Returns:
            Dictionary with extracted treatments or None
        """
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        pmid = paper.get("pmid", "")

        if not title and not abstract:
            logger.warning(f"Paper {pmid} has no title or abstract")
            return None

        # Create prompt for extraction
        prompt = self._create_extraction_prompt(title, abstract)

        for attempt in range(retry_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a medical research analyst specializing in autism treatments. Extract pharmacological interventions from research papers with precision.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                )

                content = response.choices[0].message.content
                result = json.loads(content)

                # Validate and enrich result
                enriched = self._enrich_result(result, paper)

                if enriched and enriched.get("treatments"):
                    logger.info(
                        f"Extracted {len(enriched['treatments'])} treatments from paper {pmid}"
                    )
                    return enriched
                else:
                    logger.info(f"No treatments found in paper {pmid}")
                    return None

            except json.JSONDecodeError as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{retry_attempts} - "
                    f"Invalid JSON response for paper {pmid}: {e}"
                )
                if attempt < retry_attempts - 1:
                    continue
                else:
                    logger.error(f"Failed to parse response after all attempts")
                    return None

            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{retry_attempts} - "
                    f"Error extracting treatments for paper {pmid}: {e}"
                )
                if attempt < retry_attempts - 1:
                    continue
                else:
                    logger.error(
                        f"Failed to extract treatments after all attempts: {e}"
                    )
                    return None

        return None

    def _create_extraction_prompt(self, title: str, abstract: str) -> str:
        """Create extraction prompt for LLM.

        Args:
            title: Paper title
            abstract: Paper abstract

        Returns:
            Extraction prompt
        """
        return f"""Analyze this research paper and extract ALL pharmacological treatments or interventions mentioned for autism.

Title: {title}

Abstract: {abstract}

For each pharmacological treatment found, extract:
1. Drug/medication name (generic and brand names if available)
2. Drug class/category (e.g., SSRI, antipsychotic, stimulant)
3. Mechanism of action if mentioned
4. Dosage information if specified
5. Specific autism traits or symptoms targeted
6. Outcome/efficacy mentioned in the study
7. Any adverse effects mentioned

Return ONLY treatments that are pharmacological (drugs, medications, supplements with clear chemical compounds).
Do NOT include behavioral therapies, educational interventions, or non-pharmacological treatments.

Return a JSON object with this structure:
{{
  "has_pharmacological_treatment": true/false,
  "treatments": [
    {{
      "drug_name": "string (primary name)",
      "alternative_names": ["list of alternative names"],
      "drug_class": "string",
      "mechanism_of_action": "string or null",
      "dosage": "string or null",
      "target_symptoms": ["list of symptoms/traits"],
      "outcomes": "string describing efficacy",
      "adverse_effects": ["list of side effects"] or null,
      "study_type": "RCT/observational/case study/review/etc"
    }}
  ],
  "notes": "any additional relevant information"
}}

If no pharmacological treatments are mentioned, return {{"has_pharmacological_treatment": false, "treatments": [], "notes": ""}}.
"""

    def _enrich_result(
        self, result: Dict[str, any], paper: Dict[str, any]
    ) -> Optional[Dict[str, any]]:
        """Enrich extraction result with paper metadata.

        Args:
            result: Extraction result from LLM
            paper: Original paper data

        Returns:
            Enriched result
        """
        if not result.get("has_pharmacological_treatment"):
            return None

        enriched = {
            "pmid": paper.get("pmid"),
            "paper_title": paper.get("title"),
            "paper_authors": paper.get("authors", []),
            "paper_journal": paper.get("journal"),
            "paper_year": paper.get("year"),
            "has_pharmacological_treatment": True,
            "treatments": result.get("treatments", []),
            "notes": result.get("notes", ""),
            "extraction_metadata": {
                "model": self.model,
                "timestamp": None,  # Will be set in pipeline
            },
        }

        # Normalize and validate treatments
        treatments = []
        for treatment in enriched.get("treatments", []):
            if self._validate_treatment(treatment):
                treatments.append(self._normalize_treatment(treatment))

        enriched["treatments"] = treatments

        return enriched if treatments else None

    def _validate_treatment(self, treatment: Dict[str, any]) -> bool:
        """Validate a treatment entry.

        Args:
            treatment: Treatment dictionary

        Returns:
            True if valid
        """
        return bool(treatment.get("drug_name"))

    def _normalize_treatment(self, treatment: Dict[str, any]) -> Dict[str, any]:
        """Normalize treatment data.

        Args:
            treatment: Treatment dictionary

        Returns:
            Normalized treatment
        """
        return {
            "drug_name": treatment.get("drug_name", "").strip(),
            "alternative_names": [
                name.strip()
                for name in treatment.get("alternative_names", [])
                if name.strip()
            ],
            "drug_class": treatment.get("drug_class", "").strip() or None,
            "mechanism_of_action": treatment.get("mechanism_of_action") or None,
            "dosage": treatment.get("dosage") or None,
            "target_symptoms": [
                symptom.strip()
                for symptom in treatment.get("target_symptoms", [])
                if symptom.strip()
            ],
            "outcomes": treatment.get("outcomes") or None,
            "adverse_effects": treatment.get("adverse_effects") or [],
            "study_type": treatment.get("study_type") or None,
        }

    def batch_extract_treatments(
        self, papers: List[Dict[str, any]]
    ) -> List[Dict[str, any]]:
        """Extract treatments from multiple papers.

        Args:
            papers: List of paper dictionaries

        Returns:
            List of extraction results (only papers with treatments)
        """
        results = []

        for i, paper in enumerate(papers):
            logger.info(f"Processing paper {i+1}/{len(papers)}: {paper.get('pmid')}")

            extraction = self.extract_treatments(paper)

            if extraction:
                results.append(extraction)

        logger.info(
            f"Extracted treatments from {len(results)}/{len(papers)} papers in batch"
        )

        return results
