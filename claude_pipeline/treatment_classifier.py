"""Classify and organize autism treatments into hierarchical structure."""

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Set

import openai

logger = logging.getLogger(__name__)


class TreatmentClassifier:
    """Classifies and organizes autism treatments hierarchically."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 4000,
        temperature: float = 0.1,
    ):
        """Initialize treatment classifier.

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

    def build_treatment_hierarchy(
        self, treatment_records: List[Dict[str, any]]
    ) -> Dict[str, any]:
        """Build hierarchical classification of all treatments.

        Args:
            treatment_records: List of treatment extraction records

        Returns:
            Hierarchical structure of treatments
        """
        # Collect all unique treatments
        treatments_map = self._collect_unique_treatments(treatment_records)

        logger.info(f"Found {len(treatments_map)} unique drug treatments")

        # Group by drug class
        class_groups = self._group_by_class(treatments_map)

        # Create hierarchy using LLM
        hierarchy = self._create_hierarchy_with_llm(class_groups, treatments_map)

        # Add statistics
        hierarchy["statistics"] = self._calculate_statistics(
            treatment_records, treatments_map
        )

        # Add metadata
        hierarchy["metadata"] = {
            "total_papers_analyzed": len(treatment_records),
            "total_unique_drugs": len(treatments_map),
            "total_drug_classes": len(hierarchy.get("drug_classes", [])),
            "generated_at": datetime.utcnow().isoformat(),
        }

        return hierarchy

    def _collect_unique_treatments(
        self, treatment_records: List[Dict[str, any]]
    ) -> Dict[str, Dict[str, any]]:
        """Collect and merge information about unique treatments.

        Args:
            treatment_records: List of extraction records

        Returns:
            Dictionary mapping drug names to aggregated information
        """
        treatments_map = defaultdict(
            lambda: {
                "drug_name": "",
                "alternative_names": set(),
                "drug_classes": set(),
                "mechanisms": set(),
                "target_symptoms": set(),
                "study_types": set(),
                "papers": [],
                "outcomes": [],
                "adverse_effects": set(),
            }
        )

        for record in treatment_records:
            pmid = record.get("pmid")

            for treatment in record.get("treatments", []):
                drug_name = treatment.get("drug_name", "").strip().lower()

                if not drug_name:
                    continue

                # Aggregate information
                entry = treatments_map[drug_name]
                entry["drug_name"] = treatment.get("drug_name", "").strip()

                # Alternative names
                for alt_name in treatment.get("alternative_names", []):
                    if alt_name:
                        entry["alternative_names"].add(alt_name.strip())

                # Drug class
                if treatment.get("drug_class"):
                    entry["drug_classes"].add(treatment["drug_class"].strip())

                # Mechanism
                if treatment.get("mechanism_of_action"):
                    entry["mechanisms"].add(treatment["mechanism_of_action"].strip())

                # Target symptoms
                for symptom in treatment.get("target_symptoms", []):
                    if symptom:
                        entry["target_symptoms"].add(symptom.strip())

                # Study type
                if treatment.get("study_type"):
                    entry["study_types"].add(treatment["study_type"].strip())

                # Paper reference
                entry["papers"].append(
                    {
                        "pmid": pmid,
                        "title": record.get("paper_title"),
                        "year": record.get("paper_year"),
                    }
                )

                # Outcomes
                if treatment.get("outcomes"):
                    entry["outcomes"].append(treatment["outcomes"])

                # Adverse effects
                for effect in treatment.get("adverse_effects", []):
                    if effect:
                        entry["adverse_effects"].add(effect.strip())

        # Convert sets to lists for JSON serialization
        for drug_name in treatments_map:
            entry = treatments_map[drug_name]
            entry["alternative_names"] = sorted(list(entry["alternative_names"]))
            entry["drug_classes"] = sorted(list(entry["drug_classes"]))
            entry["mechanisms"] = sorted(list(entry["mechanisms"]))
            entry["target_symptoms"] = sorted(list(entry["target_symptoms"]))
            entry["study_types"] = sorted(list(entry["study_types"]))
            entry["adverse_effects"] = sorted(list(entry["adverse_effects"]))
            entry["paper_count"] = len(entry["papers"])

        return dict(treatments_map)

    def _group_by_class(
        self, treatments_map: Dict[str, Dict[str, any]]
    ) -> Dict[str, List[str]]:
        """Group drugs by their classes.

        Args:
            treatments_map: Dictionary of treatments

        Returns:
            Dictionary mapping drug classes to lists of drug names
        """
        class_groups = defaultdict(list)

        for drug_name, info in treatments_map.items():
            drug_classes = info.get("drug_classes", [])

            if drug_classes:
                for drug_class in drug_classes:
                    class_groups[drug_class].append(drug_name)
            else:
                class_groups["Unclassified"].append(drug_name)

        return dict(class_groups)

    def _create_hierarchy_with_llm(
        self,
        class_groups: Dict[str, List[str]],
        treatments_map: Dict[str, Dict[str, any]],
    ) -> Dict[str, any]:
        """Use LLM to create a comprehensive hierarchy.

        Args:
            class_groups: Drugs grouped by class
            treatments_map: Full treatment information

        Returns:
            Hierarchical structure
        """
        # Create summary for LLM
        summary = self._create_hierarchy_prompt(class_groups, treatments_map)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a pharmaceutical classification expert. Create comprehensive hierarchical classifications of medications.",
                    },
                    {"role": "user", "content": summary},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            hierarchy = json.loads(content)

            # Merge LLM hierarchy with detailed data
            enriched_hierarchy = self._enrich_hierarchy(
                hierarchy, class_groups, treatments_map
            )

            return enriched_hierarchy

        except Exception as e:
            logger.error(f"Error creating hierarchy with LLM: {e}")
            # Fallback to basic hierarchy
            return self._create_basic_hierarchy(class_groups, treatments_map)

    def _create_hierarchy_prompt(
        self,
        class_groups: Dict[str, List[str]],
        treatments_map: Dict[str, Dict[str, any]],
    ) -> str:
        """Create prompt for hierarchy generation.

        Args:
            class_groups: Drugs grouped by class
            treatments_map: Full treatment information

        Returns:
            Prompt string
        """
        # Summarize drug classes
        class_summary = []
        for drug_class, drugs in sorted(class_groups.items()):
            class_summary.append(f"- {drug_class}: {len(drugs)} drugs")

        prompt = f"""Create a comprehensive hierarchical classification system for autism pharmacological treatments.

Drug Classes Found ({len(class_groups)}):
{chr(10).join(class_summary)}

Create a JSON structure with:
1. Primary categories (e.g., "Psychotropic Medications", "Supplements", "Hormonal Treatments")
2. Secondary categories (drug classes like "SSRIs", "Antipsychotics", "Stimulants")
3. Therapeutic purpose (e.g., "Core autism symptoms", "Co-occurring conditions")

Return a JSON object with this structure:
{{
  "drug_classes": [
    {{
      "primary_category": "string",
      "secondary_category": "string",
      "class_name": "string (exact match from the list above)",
      "therapeutic_purpose": ["list of purposes"],
      "description": "brief description"
    }}
  ],
  "primary_categories": {{
    "category_name": {{
      "description": "string",
      "drug_classes": ["list of class names in this category"]
    }}
  }}
}}

Be thorough and create meaningful categories that help understand the landscape of autism treatments.
"""

        return prompt

    def _enrich_hierarchy(
        self,
        hierarchy: Dict[str, any],
        class_groups: Dict[str, List[str]],
        treatments_map: Dict[str, Dict[str, any]],
    ) -> Dict[str, any]:
        """Enrich LLM-generated hierarchy with detailed drug data.

        Args:
            hierarchy: Basic hierarchy from LLM
            class_groups: Drugs grouped by class
            treatments_map: Full treatment information

        Returns:
            Enriched hierarchy
        """
        # Add detailed drug information to each class
        for drug_class_info in hierarchy.get("drug_classes", []):
            class_name = drug_class_info.get("class_name")

            if class_name in class_groups:
                drugs_in_class = []

                for drug_name in class_groups[class_name]:
                    drug_info = treatments_map.get(drug_name, {})
                    drugs_in_class.append(
                        {
                            "drug_name": drug_info.get("drug_name"),
                            "alternative_names": drug_info.get("alternative_names", []),
                            "mechanisms": drug_info.get("mechanisms", []),
                            "target_symptoms": drug_info.get("target_symptoms", []),
                            "paper_count": drug_info.get("paper_count", 0),
                            "study_types": drug_info.get("study_types", []),
                        }
                    )

                drug_class_info["drugs"] = sorted(
                    drugs_in_class, key=lambda x: x["paper_count"], reverse=True
                )
                drug_class_info["drug_count"] = len(drugs_in_class)

        return hierarchy

    def _create_basic_hierarchy(
        self,
        class_groups: Dict[str, List[str]],
        treatments_map: Dict[str, Dict[str, any]],
    ) -> Dict[str, any]:
        """Create basic hierarchy without LLM (fallback).

        Args:
            class_groups: Drugs grouped by class
            treatments_map: Full treatment information

        Returns:
            Basic hierarchical structure
        """
        drug_classes = []

        for class_name, drug_names in sorted(class_groups.items()):
            drugs_in_class = []

            for drug_name in drug_names:
                drug_info = treatments_map.get(drug_name, {})
                drugs_in_class.append(
                    {
                        "drug_name": drug_info.get("drug_name"),
                        "alternative_names": drug_info.get("alternative_names", []),
                        "mechanisms": drug_info.get("mechanisms", []),
                        "target_symptoms": drug_info.get("target_symptoms", []),
                        "paper_count": drug_info.get("paper_count", 0),
                    }
                )

            drug_classes.append(
                {
                    "class_name": class_name,
                    "drug_count": len(drugs_in_class),
                    "drugs": sorted(
                        drugs_in_class, key=lambda x: x["paper_count"], reverse=True
                    ),
                }
            )

        return {
            "drug_classes": drug_classes,
            "primary_categories": {},
        }

    def _calculate_statistics(
        self,
        treatment_records: List[Dict[str, any]],
        treatments_map: Dict[str, Dict[str, any]],
    ) -> Dict[str, any]:
        """Calculate statistics about treatments.

        Args:
            treatment_records: All treatment records
            treatments_map: Unique treatments

        Returns:
            Statistics dictionary
        """
        # Most studied drugs
        most_studied = sorted(
            treatments_map.items(), key=lambda x: x[1]["paper_count"], reverse=True
        )[:20]

        # Most common target symptoms
        all_symptoms = defaultdict(int)
        for drug_info in treatments_map.values():
            for symptom in drug_info.get("target_symptoms", []):
                all_symptoms[symptom] += 1

        top_symptoms = sorted(all_symptoms.items(), key=lambda x: x[1], reverse=True)[
            :20
        ]

        # Study type distribution
        study_types = defaultdict(int)
        for record in treatment_records:
            for treatment in record.get("treatments", []):
                study_type = treatment.get("study_type")
                if study_type:
                    study_types[study_type] += 1

        return {
            "most_studied_drugs": [
                {"drug": name, "paper_count": info["paper_count"]}
                for name, info in most_studied
            ],
            "most_common_symptoms": [
                {"symptom": symptom, "frequency": count}
                for symptom, count in top_symptoms
            ],
            "study_type_distribution": dict(study_types),
        }
