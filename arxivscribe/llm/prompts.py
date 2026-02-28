"""Prompt templates for LLM summarization."""

SUMMARY_PROMPT = """You are an expert ML research assistant. Write a concise TLDR (2-3 sentences max) for this paper.

Rules:
- Focus on: what problem, what method/approach, key result or finding
- Be technical but accessible to grad students
- No filler phrases like "This paper presents..." — just state what it does
- Include quantitative results if mentioned in the abstract

Title: {title}

Abstract: {abstract}

TLDR:"""


KEYWORD_EXTRACTION_PROMPT = """Extract 3-5 key technical keywords or phrases from this paper. Return ONLY a comma-separated list.

Title: {title}

Abstract: {abstract}

Keywords:"""


RELEVANCE_PROMPT = """Rate this paper's relevance to the interests: {interests}

Title: {title}
Abstract: {abstract}

Answer YES or NO, then one sentence explaining why:"""


WEEKLY_DIGEST_PROMPT = """Summarize these {count} papers into a cohesive 1-paragraph overview of this week's research trends. Mention the most notable findings.

Papers:
{papers_text}

Weekly Summary:"""
