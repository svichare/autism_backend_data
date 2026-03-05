from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from typing import Dict, Iterable, List, Optional

from Bio import Entrez

from .internal_datasets.base import InternalDataset

logger = logging.getLogger(__name__)


class PubMedPipeline:
    def __init__(
        self,
        dataset: InternalDataset,
        email: str,
        api_key: Optional[str] = None,
        max_results: int = 20,
        requests_per_second: float = 3.0,
        full_text: bool = True,
    ) -> None:
        self.dataset = dataset
        self.max_results = max_results
        self.requests_per_second = requests_per_second
        self.full_text = full_text

        Entrez.email = email
        if api_key:
            Entrez.api_key = api_key

    def _sleep_for_rate_limit(self) -> None:
        if self.requests_per_second <= 0:
            return
        time.sleep(1.0 / self.requests_per_second)

    def search_pmc(self, term: str) -> List[str]:
        logger.info("Searching PMC for term=%r max_results=%s", term, self.max_results)
        handle = Entrez.esearch(db="pmc", term=term, retmax=self.max_results)
        results = Entrez.read(handle)
        handle.close()
        ids = results.get("IdList", [])
        logger.info("PMC search returned %d ids", len(ids))
        return [str(i) for i in ids]

    def _normalize_pmc_id(self, pmc_id: str) -> str:
        pmc_id = str(pmc_id).strip()
        if pmc_id.upper().startswith("PMC"):
            normalized = pmc_id[3:]
            if normalized.isdigit():
                logger.debug("Normalized PMC id from %s to %s", pmc_id, normalized)
                return normalized
        return pmc_id

    def _debug_esummary_response(self, pmc_id: str) -> None:
        try:
            self._sleep_for_rate_limit()
            handle = Entrez.esummary(db="pmc", id=pmc_id, retmode="xml")
            raw = handle.read()
            handle.close()
            snippet = raw[:500] if isinstance(raw, str) else raw.decode("utf-8", errors="replace")[:500]
            logger.error("esummary raw response for PMC id=%s (first 500 chars): %s", pmc_id, snippet)
        except Exception as exc:
            logger.exception("Failed to fetch raw esummary response for PMC id=%s: %s", pmc_id, exc)

    def _entrez_item_to_value(self, item: object) -> object:
        if isinstance(item, dict):
            item_type = item.get("Type")
            if item_type == "List":
                sub_items = item.get("Item", [])
                return [self._entrez_item_to_value(sub) for sub in sub_items]
            if item_type == "Structure":
                sub_items = item.get("Item", [])
                return self._items_to_dict(sub_items)
            return item.get("#text") or item.get("Item") or item.get("Value")
        return item

    def _items_to_dict(self, items: List[Dict]) -> Dict[str, object]:
        parsed: Dict[str, object] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("Name")
            if not name:
                continue
            value = self._entrez_item_to_value(item)
            if name in parsed:
                existing = parsed[name]
                if isinstance(existing, list):
                    existing.append(value)
                else:
                    parsed[name] = [existing, value]
            else:
                parsed[name] = value
        return parsed

    def _docsum_to_dict(self, doc: Dict) -> Dict[str, object]:
        items_raw = doc.get("Item", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]
        elif isinstance(items_raw, tuple):
            items_raw = list(items_raw)
        items = self._items_to_dict(items_raw)
        doc_id = doc.get("Id")
        if doc_id is not None:
            items["Id"] = str(doc_id)
        return items

    def _text_content(self, element: Optional[ET.Element]) -> str:
        if element is None:
            return ""
        return "".join(element.itertext()).strip()

    def _parse_jats_article(self, xml_text: str, pmc_id: str) -> Dict[str, object]:
        root = ET.fromstring(xml_text)
        article = root.find(".//article")
        if article is None:
            raise ValueError("No <article> element found in JATS XML")

        title = self._text_content(article.find(".//article-title"))
        abstract = self._text_content(article.find(".//abstract"))
        journal_title = self._text_content(article.find(".//journal-title"))

        pub_date = ""
        pub_date_el = article.find(".//pub-date")
        if pub_date_el is not None:
            year = self._text_content(pub_date_el.find("year"))
            month = self._text_content(pub_date_el.find("month"))
            day = self._text_content(pub_date_el.find("day"))
            pub_date = "-".join(p for p in [year, month, day] if p)
        if not pub_date:
            pub_date = self._text_content(article.find(".//pub-date/medline-date"))

        authors = []
        for contrib in article.findall(".//contrib[@contrib-type='author']"):
            surname = self._text_content(contrib.find(".//surname"))
            given = self._text_content(contrib.find(".//given-names"))
            name = " ".join(part for part in [given, surname] if part)
            if name:
                authors.append(name)

        sections = []
        for sec in article.findall(".//body//sec"):
            sec_title = self._text_content(sec.find("title"))
            sec_text = self._text_content(sec)
            if sec_text:
                sections.append({"title": sec_title, "text": sec_text})

        return {
            "Id": pmc_id,
            "Title": title,
            "Abstract": abstract,
            "JournalTitle": journal_title,
            "PubDate": pub_date,
            "Authors": authors,
            "Sections": sections,
        }

    def fetch_full_texts(self, pmc_ids: Iterable[str]) -> List[Dict]:
        pmc_ids = list(pmc_ids)
        if not pmc_ids:
            logger.info("No new PMC ids to fetch full text for")
            return []

        documents: List[Dict] = []
        for pmc_id in pmc_ids:
            normalized_id = self._normalize_pmc_id(pmc_id)
            logger.debug("Fetching full text for PMC id=%s (normalized=%s)", pmc_id, normalized_id)
            self._sleep_for_rate_limit()
            handle = Entrez.efetch(db="pmc", id=normalized_id, retmode="xml")
            try:
                xml_text = handle.read()
            except Exception as exc:
                logger.exception("Entrez.efetch failed for PMC id=%s: %s", normalized_id, exc)
                continue
            finally:
                handle.close()

            if isinstance(xml_text, bytes):
                xml_text = xml_text.decode("utf-8", errors="replace")

            try:
                parsed = self._parse_jats_article(xml_text, normalized_id)
            except Exception as exc:
                logger.exception("Failed to parse JATS XML for PMC id=%s: %s", normalized_id, exc)
                continue

            parsed["paper_id"] = str(parsed.get("Id") or normalized_id)
            parsed["source_db"] = "pmc"
            documents.append(parsed)

        return documents

    def fetch_summaries(self, pmc_ids: Iterable[str]) -> List[Dict]:
        pmc_ids = list(pmc_ids)
        if not pmc_ids:
            logger.info("No new PMC ids to fetch summaries for")
            return []

        summaries: List[Dict] = []
        for pmc_id in pmc_ids:
            normalized_id = self._normalize_pmc_id(pmc_id)
            logger.debug("Fetching summary for PMC id=%s (normalized=%s)", pmc_id, normalized_id)
            self._sleep_for_rate_limit()
            handle = Entrez.esummary(db="pmc", id=normalized_id)
            try:
                record = Entrez.read(handle)
            except Exception as exc:
                logger.exception("Entrez.read failed for PMC id=%s: %s", normalized_id, exc)
                self._debug_esummary_response(normalized_id)
                continue
            finally:
                handle.close()
            logger.debug("esummary record for PMC id=%s: %r", normalized_id, record)
            if not isinstance(record, list) or not record or not isinstance(record[0], dict):
                logger.warning("Unexpected esummary record shape for PMC id=%s", normalized_id)
                logger.debug("esummary record for PMC id=%s: %r", normalized_id, record)
                self._debug_esummary_response(normalized_id)
                continue

            doc = record[0]
            document = {k: v for k, v in doc.items() if k != "Item"}
            doc_id = document.get("Id") or normalized_id
            document["paper_id"] = str(doc_id)
            document["source_db"] = "pmc"
            summaries.append(document)
        return summaries

    def run(self, term: str) -> Dict[str, int]:
        logger.info("Pipeline run started")
        pmc_ids = self.search_pmc(term)

        logger.info("Checking %d ids against internal dataset", len(pmc_ids))
        new_ids = [pid for pid in pmc_ids if not self.dataset.exists(pid)]
        logger.info("New ids=%d existing=%d", len(new_ids), len(pmc_ids) - len(new_ids))
        if self.full_text:
            documents = self.fetch_full_texts(new_ids)
            logger.info("Fetched %d full text documents, writing to dataset", len(documents))
            self.dataset.add_many(documents)
            new_written = len(documents)
        else:
            summaries = self.fetch_summaries(new_ids)
            logger.info("Fetched %d summaries, writing to dataset", len(summaries))
            self.dataset.add_many(summaries)
            new_written = len(summaries)
        logger.info("Pipeline run complete")

        return {
            "found": len(pmc_ids),
            "new": new_written,
            "skipped_existing": len(pmc_ids) - len(new_ids),
        }
