"""NCBI/PubMed paper fetcher with pagination and rate limiting."""

import logging
import time
from typing import Dict, Iterator, List, Optional
from xml.etree import ElementTree as ET

from Bio import Entrez

logger = logging.getLogger(__name__)


class NCBIFetcher:
    """Fetches papers from NCBI/PubMed with proper rate limiting."""

    def __init__(
        self,
        api_key: str,
        email: str,
        rate_limit_delay: float = 0.34,
    ):
        """Initialize NCBI fetcher.

        Args:
            api_key: NCBI API key
            email: Email for NCBI API
            rate_limit_delay: Delay between requests (default ~3 requests/sec)
        """
        self.api_key = api_key
        self.email = email
        self.rate_limit_delay = rate_limit_delay

        Entrez.email = email
        Entrez.api_key = api_key

    def _rate_limit(self) -> None:
        """Apply rate limiting delay."""
        time.sleep(self.rate_limit_delay)

    def search_papers(
        self,
        term: str,
        max_results: Optional[int] = None,
        retstart: int = 0,
        retmax: int = 10000,
    ) -> Dict[str, any]:
        """Search for papers in PubMed.

        Args:
            term: Search term
            max_results: Maximum total results to return (None for all)
            retstart: Starting position in results
            retmax: Maximum results per batch

        Returns:
            Dict with 'count', 'ids', and 'retstart'
        """
        self._rate_limit()

        try:
            handle = Entrez.esearch(
                db="pubmed",
                term=term,
                retstart=retstart,
                retmax=retmax,
                usehistory="y",
            )
            result = Entrez.read(handle)
            handle.close()

            count = int(result.get("Count", 0))
            ids = result.get("IdList", [])
            webenv = result.get("WebEnv")
            query_key = result.get("QueryKey")

            logger.info(
                f"Search found {count} total papers, "
                f"fetched {len(ids)} IDs starting from {retstart}"
            )

            return {
                "count": count,
                "ids": [str(i) for i in ids],
                "webenv": webenv,
                "query_key": query_key,
                "retstart": retstart,
            }

        except Exception as e:
            logger.error(f"Error searching PubMed: {e}")
            raise

    def fetch_paper_details(
        self, pmids: List[str], retry_attempts: int = 3
    ) -> List[Dict[str, any]]:
        """Fetch detailed information for papers.

        Args:
            pmids: List of PubMed IDs
            retry_attempts: Number of retry attempts

        Returns:
            List of paper details
        """
        if not pmids:
            return []

        for attempt in range(retry_attempts):
            try:
                self._rate_limit()

                # Fetch paper details using efetch
                handle = Entrez.efetch(
                    db="pubmed",
                    id=",".join(pmids),
                    retmode="xml",
                )
                xml_data = handle.read()
                handle.close()

                # Parse XML
                papers = self._parse_pubmed_xml(xml_data)
                logger.info(f"Fetched details for {len(papers)} papers")
                return papers

            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{retry_attempts} failed "
                    f"fetching paper details: {e}"
                )
                if attempt < retry_attempts - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to fetch paper details after all attempts")
                    raise

        return []

    def _parse_pubmed_xml(self, xml_data: bytes) -> List[Dict[str, any]]:
        """Parse PubMed XML response.

        Args:
            xml_data: XML data from PubMed

        Returns:
            List of parsed papers
        """
        papers = []

        try:
            root = ET.fromstring(xml_data)

            for article in root.findall(".//PubmedArticle"):
                paper = self._extract_paper_info(article)
                if paper:
                    papers.append(paper)

        except Exception as e:
            logger.error(f"Error parsing PubMed XML: {e}")
            raise

        return papers

    def _extract_paper_info(self, article: ET.Element) -> Optional[Dict[str, any]]:
        """Extract information from a PubMed article element.

        Args:
            article: PubMed article XML element

        Returns:
            Dictionary with paper information
        """
        try:
            medline = article.find(".//MedlineCitation")
            if medline is None:
                return None

            pmid_elem = medline.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else None

            # Title
            title_elem = medline.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else ""

            # Abstract
            abstract_parts = []
            abstract_node = medline.find(".//Abstract")
            if abstract_node is not None:
                for abstract_text in abstract_node.findall(".//AbstractText"):
                    label = abstract_text.get("Label", "")
                    text = "".join(abstract_text.itertext()).strip()
                    if label:
                        abstract_parts.append(f"{label}: {text}")
                    else:
                        abstract_parts.append(text)

            abstract = " ".join(abstract_parts)

            # Authors
            authors = []
            author_list = medline.find(".//AuthorList")
            if author_list is not None:
                for author in author_list.findall(".//Author"):
                    last_name = author.find("LastName")
                    fore_name = author.find("ForeName")
                    if last_name is not None:
                        name = last_name.text or ""
                        if fore_name is not None and fore_name.text:
                            name = f"{fore_name.text} {name}"
                        authors.append(name)

            # Journal
            journal_elem = medline.find(".//Journal/Title")
            journal = journal_elem.text if journal_elem is not None else ""

            # Publication date
            pub_date = medline.find(".//PubDate")
            year = ""
            if pub_date is not None:
                year_elem = pub_date.find("Year")
                year = year_elem.text if year_elem is not None else ""

            # Keywords/MeSH terms
            keywords = []
            keyword_list = medline.find(".//KeywordList")
            if keyword_list is not None:
                for keyword in keyword_list.findall(".//Keyword"):
                    if keyword.text:
                        keywords.append(keyword.text)

            mesh_headings = medline.findall(".//MeshHeading/DescriptorName")
            for mesh in mesh_headings:
                if mesh.text and mesh.text not in keywords:
                    keywords.append(mesh.text)

            return {
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "journal": journal,
                "year": year,
                "keywords": keywords,
                "source": "pubmed",
            }

        except Exception as e:
            logger.warning(f"Error extracting paper info: {e}")
            return None

    def fetch_papers_iterator(
        self,
        term: str,
        max_total: Optional[int] = None,
        batch_size: int = 100,
        start_from: int = 0,
    ) -> Iterator[List[Dict[str, any]]]:
        """Iterator that yields batches of papers.

        Args:
            term: Search term
            max_total: Maximum total papers to fetch (None for unlimited)
            batch_size: Number of papers per batch
            start_from: Starting position (for resuming)

        Yields:
            Batches of paper details
        """
        # First search to get total count
        search_result = self.search_papers(term, retstart=0, retmax=1)
        total_available = search_result["count"]

        logger.info(
            f"Found {total_available} total papers for term '{term}', "
            f"fetching up to {max_total or 'unlimited'} papers"
        )

        if max_total:
            total_to_fetch = min(total_available, max_total)
        else:
            total_to_fetch = total_available

        fetched = start_from

        while fetched < total_to_fetch:
            # Determine batch size for this iteration
            current_batch_size = min(batch_size, total_to_fetch - fetched)

            # Search for IDs in this batch
            search_result = self.search_papers(
                term, retstart=fetched, retmax=current_batch_size
            )

            pmids = search_result["ids"]

            if not pmids:
                logger.warning(f"No more papers found at position {fetched}")
                break

            # Fetch detailed information
            papers = self.fetch_paper_details(pmids)

            if papers:
                yield papers
                fetched += len(papers)
                logger.info(
                    f"Progress: {fetched}/{total_to_fetch} papers fetched "
                    f"({100*fetched/total_to_fetch:.1f}%)"
                )
            else:
                logger.warning(f"No papers fetched in this batch")
                fetched += len(pmids)  # Skip these IDs
