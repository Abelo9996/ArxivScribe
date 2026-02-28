"""TF-IDF based paper similarity for 'more like this' recommendations."""
import math
import re
from typing import List, Dict, Tuple
from collections import Counter


class PaperSimilarity:
    """Lightweight TF-IDF similarity — no external deps needed."""

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Simple tokenization: lowercase, alphanum only, remove stopwords."""
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these',
            'those', 'it', 'its', 'we', 'our', 'their', 'they', 'which', 'what',
            'who', 'whom', 'how', 'when', 'where', 'than', 'then', 'also', 'as',
            'not', 'no', 'nor', 'so', 'if', 'each', 'every', 'all', 'both',
            'such', 'into', 'over', 'after', 'before', 'between', 'under', 'above',
            'up', 'down', 'out', 'about', 'through', 'during', 'paper', 'propose',
            'proposed', 'show', 'shown', 'using', 'used', 'results', 'approach',
            'method', 'methods', 'based', 'model', 'models', 'new', 'novel',
        }
        tokens = re.findall(r'[a-z][a-z0-9]+', text.lower())
        return [t for t in tokens if t not in stopwords and len(t) > 2]

    @staticmethod
    def build_tfidf(documents: List[List[str]]) -> Tuple[List[Dict[str, float]], Dict[str, float]]:
        """Build TF-IDF vectors for a set of documents."""
        n = len(documents)
        if n == 0:
            return [], {}

        # Document frequency
        df = Counter()
        for doc in documents:
            df.update(set(doc))

        # IDF
        idf = {term: math.log(n / (1 + freq)) for term, freq in df.items()}

        # TF-IDF per document
        vectors = []
        for doc in documents:
            tf = Counter(doc)
            total = len(doc) or 1
            vec = {term: (count / total) * idf.get(term, 0) for term, count in tf.items()}
            vectors.append(vec)

        return vectors, idf

    @staticmethod
    def cosine_sim(a: Dict[str, float], b: Dict[str, float]) -> float:
        """Cosine similarity between two sparse vectors."""
        common = set(a.keys()) & set(b.keys())
        if not common:
            return 0.0

        dot = sum(a[k] * b[k] for k in common)
        norm_a = math.sqrt(sum(v ** 2 for v in a.values()))
        norm_b = math.sqrt(sum(v ** 2 for v in b.values()))

        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @classmethod
    def find_similar(cls, target_paper: dict, all_papers: List[dict], top_k: int = 5) -> List[Tuple[dict, float]]:
        """Find papers most similar to target_paper."""
        if not all_papers:
            return []

        # Build text from title + abstract
        def paper_text(p):
            return f"{p.get('title', '')} {p.get('abstract', '')}"

        target_tokens = cls.tokenize(paper_text(target_paper))
        all_tokens = [cls.tokenize(paper_text(p)) for p in all_papers]

        # Include target in corpus for proper IDF
        all_docs = [target_tokens] + all_tokens
        vectors, _ = cls.build_tfidf(all_docs)

        target_vec = vectors[0]
        similarities = []

        for i, paper in enumerate(all_papers):
            if paper.get('id') == target_paper.get('id'):
                continue
            sim = cls.cosine_sim(target_vec, vectors[i + 1])
            if sim > 0.01:
                similarities.append((paper, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
