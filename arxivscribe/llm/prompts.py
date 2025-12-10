"""Prompt templates for LLM summarization."""

SUMMARY_PROMPT = """You are an expert AI research assistant. Generate a concise TLDR summary (1-3 sentences) for the following research paper.

Focus on:
- What problem the paper addresses
- What the paper introduces or proposes
- Key contributions or findings

Keep it technical but accessible.

Title: {title}

Abstract: {abstract}

TLDR:"""


KEYWORD_EXTRACTION_PROMPT = """Extract 3-5 key technical keywords or phrases from this paper that best represent its main topics and contributions.

Title: {title}

Abstract: {abstract}

Keywords (comma-separated):"""


RELEVANCE_PROMPT = """Determine if this paper is relevant to the following research interests: {interests}

Title: {title}

Abstract: {abstract}

Answer with YES or NO, followed by a brief explanation:"""
