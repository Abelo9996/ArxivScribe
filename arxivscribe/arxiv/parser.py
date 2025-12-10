"""Parser for arXiv API XML responses."""
import xml.etree.ElementTree as ET
import logging
from typing import List
from datetime import datetime

logger = logging.getLogger(__name__)


class ArxivParser:
    """Parses arXiv API XML responses into structured data."""

    # XML namespaces
    ATOM_NS = "{http://www.w3.org/2005/Atom}"
    ARXIV_NS = "{http://arxiv.org/schemas/atom}"

    def parse_response(self, xml_content: str) -> List[dict]:
        """
        Parse arXiv API XML response.
        
        Args:
            xml_content: XML response string
            
        Returns:
            List of paper dictionaries
        """
        papers = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # Find all entry elements
            entries = root.findall(f"{self.ATOM_NS}entry")
            
            for entry in entries:
                paper = self._parse_entry(entry)
                if paper:
                    papers.append(paper)
            
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
        except Exception as e:
            logger.error(f"Error parsing arXiv response: {e}")
        
        return papers

    def _parse_entry(self, entry: ET.Element) -> dict:
        """
        Parse a single entry element.
        
        Args:
            entry: XML entry element
            
        Returns:
            Paper dictionary
        """
        try:
            # Extract ID from URL
            id_elem = entry.find(f"{self.ATOM_NS}id")
            arxiv_url = id_elem.text if id_elem is not None else ""
            arxiv_id = arxiv_url.split("/abs/")[-1] if "/abs/" in arxiv_url else ""
            
            # Title
            title_elem = entry.find(f"{self.ATOM_NS}title")
            title = title_elem.text.strip() if title_elem is not None else "Unknown"
            
            # Abstract
            summary_elem = entry.find(f"{self.ATOM_NS}summary")
            abstract = summary_elem.text.strip() if summary_elem is not None else ""
            
            # Authors
            authors = []
            for author in entry.findall(f"{self.ATOM_NS}author"):
                name_elem = author.find(f"{self.ATOM_NS}name")
                if name_elem is not None:
                    authors.append(name_elem.text)
            
            # Published date
            published_elem = entry.find(f"{self.ATOM_NS}published")
            published = published_elem.text if published_elem is not None else ""
            
            # Updated date
            updated_elem = entry.find(f"{self.ATOM_NS}updated")
            updated = updated_elem.text if updated_elem is not None else ""
            
            # Categories
            categories = []
            for category in entry.findall(f"{self.ATOM_NS}category"):
                term = category.get("term")
                if term:
                    categories.append(term)
            
            # PDF link
            pdf_url = ""
            for link in entry.findall(f"{self.ATOM_NS}link"):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href", "")
                    break
            
            # Primary category
            primary_cat_elem = entry.find(f"{self.ARXIV_NS}primary_category")
            primary_category = primary_cat_elem.get("term") if primary_cat_elem is not None else ""
            
            paper = {
                "id": arxiv_id,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "published": published,
                "updated": updated,
                "categories": categories,
                "primary_category": primary_category,
                "url": arxiv_url,
                "pdf_url": pdf_url
            }
            
            return paper
            
        except Exception as e:
            logger.error(f"Error parsing entry: {e}")
            return None

    @staticmethod
    def format_date(date_string: str) -> str:
        """
        Format arXiv date string to readable format.
        
        Args:
            date_string: ISO format date string
            
        Returns:
            Formatted date string
        """
        try:
            dt = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
            return dt.strftime("%B %d, %Y")
        except Exception:
            return date_string
