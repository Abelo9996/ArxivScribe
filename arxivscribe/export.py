"""Export papers to various formats."""
from typing import List
import csv
import json
import io
import re


def export_bibtex(papers: List[dict]) -> str:
    """Export papers to BibTeX format."""
    entries = []
    for paper in papers:
        arxiv_id = paper.get('id', '').replace('/', '_').replace('.', '_')
        authors_raw = paper.get('authors', [])
        if isinstance(authors_raw, str):
            authors_raw = [a.strip() for a in authors_raw.split(',')]
        authors = " and ".join(authors_raw) if authors_raw else "Unknown"

        title = paper.get('title', 'Untitled')
        year = paper.get('published', '')[:4] or '2024'
        url = paper.get('url', '')
        abstract = paper.get('abstract', '')

        # Clean for BibTeX
        title = title.replace('{', '\\{').replace('}', '\\}')
        abstract = abstract.replace('{', '\\{').replace('}', '\\}')

        key = f"arxiv_{arxiv_id}_{year}" if arxiv_id else f"paper_{year}"

        entry = f"""@article{{{key},
  title = {{{title}}},
  author = {{{authors}}},
  year = {{{year}}},
  url = {{{url}}},
  eprint = {{{paper.get('id', '')}}},
  archivePrefix = {{arXiv}},
  primaryClass = {{{paper.get('primary_category', '')}}},
  abstract = {{{abstract[:500]}}}
}}"""
        entries.append(entry)

    return "\n\n".join(entries)


def export_markdown(papers: List[dict]) -> str:
    """Export papers to Markdown."""
    lines = ["# ArxivScribe Paper Export", ""]

    for i, paper in enumerate(papers, 1):
        title = paper.get('title', 'Untitled')
        url = paper.get('url', '')
        authors_raw = paper.get('authors', [])
        if isinstance(authors_raw, str):
            authors_raw = [a.strip() for a in authors_raw.split(',')]
        authors = ", ".join(authors_raw[:5])
        if len(authors_raw) > 5:
            authors += f" +{len(authors_raw) - 5} more"

        date = (paper.get('published', '') or '')[:10]
        summary = paper.get('summary', '')
        categories = paper.get('categories', [])
        if isinstance(categories, str):
            categories = [c.strip() for c in categories.split(',')]
        pdf = paper.get('pdf_url', '')

        lines.append(f"## {i}. [{title}]({url})")
        lines.append(f"**Authors:** {authors}")
        lines.append(f"**Date:** {date} | **Categories:** {', '.join(categories[:5])}")
        if summary:
            lines.append(f"\n> {summary}")
        if pdf:
            lines.append(f"\n[PDF]({pdf})")
        lines.append("")

    lines.append(f"\n---\n*Exported by [ArxivScribe](https://github.com/Abelo9996/ArxivScribe) — {len(papers)} papers*")
    return "\n".join(lines)


def export_csv(papers: List[dict]) -> str:
    """Export papers to CSV."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'arxiv_id', 'title', 'authors', 'published', 'categories',
        'abstract', 'summary', 'url', 'pdf_url', 'score'
    ])

    for paper in papers:
        authors = paper.get('authors', [])
        if isinstance(authors, list):
            authors = "; ".join(authors)
        categories = paper.get('categories', [])
        if isinstance(categories, list):
            categories = "; ".join(categories)

        writer.writerow([
            paper.get('id', ''),
            paper.get('title', ''),
            authors,
            (paper.get('published', '') or '')[:10],
            categories,
            paper.get('abstract', ''),
            paper.get('summary', ''),
            paper.get('url', ''),
            paper.get('pdf_url', ''),
            paper.get('score', 0)
        ])

    return output.getvalue()


def export_json(papers: List[dict]) -> str:
    """Export papers to JSON."""
    clean = []
    for paper in papers:
        clean.append({
            'arxiv_id': paper.get('id', ''),
            'title': paper.get('title', ''),
            'authors': paper.get('authors', []),
            'published': paper.get('published', ''),
            'categories': paper.get('categories', []),
            'primary_category': paper.get('primary_category', ''),
            'abstract': paper.get('abstract', ''),
            'summary': paper.get('summary', ''),
            'url': paper.get('url', ''),
            'pdf_url': paper.get('pdf_url', ''),
            'score': paper.get('score', 0),
        })
    return json.dumps(clean, indent=2, ensure_ascii=False)
