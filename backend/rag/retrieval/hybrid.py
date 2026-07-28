import math
import re
from collections import Counter

from rag.chunker.recursive import split_markdown
from rag.reranker.rrf import reciprocal_rank_fusion
from rag.retrieval.query_rewriter import rewrite_query


class HybridRetriever:
    def __init__(self, document_service) -> None:
        self.document_service = document_service

    def search(
        self,
        query: str,
        scope: dict[str, str],
        top_k: int = 5,
        filters: dict | None = None,
    ) -> dict:
        rewritten = rewrite_query(query)
        filters = filters or {}
        documents = [
            doc
            for doc in self.document_service.all_visible_text(scope)
            if self._match_filters(doc, filters)
        ]
        chunks = self._build_chunks(documents)
        if not chunks:
            return {
                "rewritten_query": rewritten,
                "results": [],
                "retrieval_meta": {
                    "strategy": "chunked_hybrid_rrf",
                    "document_count": len(documents),
                    "chunk_count": 0,
                    "rankers": [],
                    "filters": filters,
                },
            }

        query_terms = self._tokenize(rewritten)
        keyword_ranking = self._keyword_rank(chunks, query_terms)
        semantic_ranking = self._semantic_rank(chunks, rewritten, query_terms)
        metadata_ranking = self._metadata_rank(chunks, rewritten, query_terms)
        fused = reciprocal_rank_fusion(
            [
                keyword_ranking[:30],
                semantic_ranking[:30],
                metadata_ranking[:30],
            ]
        )

        results = [self._format_hit(item) for item in fused[:top_k]]
        return {
            "rewritten_query": rewritten,
            "results": results,
            "retrieval_meta": {
                "strategy": "chunked_hybrid_rrf",
                "document_count": len(documents),
                "chunk_count": len(chunks),
                "rankers": [
                    {"name": "bm25_keyword", "hit_count": len(keyword_ranking)},
                    {"name": "local_semantic", "hit_count": len(semantic_ranking)},
                    {"name": "metadata", "hit_count": len(metadata_ranking)},
                ],
                "filters": filters,
            },
        }

    def _build_chunks(self, documents: list[dict]) -> list[dict]:
        chunks: list[dict] = []
        for doc in documents:
            for chunk in split_markdown(doc["content"]):
                chunk_id = f"{doc['id']}:{chunk['chunk_index']}"
                chunks.append(
                    {
                        **doc,
                        "chunk_id": chunk_id,
                        "chunk_index": chunk["chunk_index"],
                        "section": chunk["section"],
                        "chunk_text": chunk["text"],
                        "chunk_terms": self._tokenize(
                            f"{doc['title']} {' '.join(doc['tags'])} {chunk['section']} {chunk['text']}"
                        ),
                    }
                )
        return chunks

    def _keyword_rank(self, chunks: list[dict], query_terms: list[str]) -> list[dict]:
        if not query_terms:
            return []

        query_counts = Counter(query_terms)
        doc_freq: Counter[str] = Counter()
        chunk_counts = []
        for chunk in chunks:
            counts = Counter(chunk["chunk_terms"])
            chunk_counts.append(counts)
            doc_freq.update(counts.keys())

        avg_len = sum(sum(counts.values()) for counts in chunk_counts) / max(len(chunk_counts), 1)
        ranked = []
        for chunk, counts in zip(chunks, chunk_counts):
            length = sum(counts.values()) or 1
            score = 0.0
            for term, query_count in query_counts.items():
                tf = counts.get(term, 0)
                if not tf:
                    continue
                idf = math.log(1 + (len(chunks) - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
                denominator = tf + 1.5 * (1 - 0.75 + 0.75 * length / max(avg_len, 1))
                score += idf * ((tf * 2.5) / denominator) * query_count
            if score > 0:
                ranked.append(
                    {**chunk, "keyword_score": round(score, 4), "rank_source": "bm25_keyword", "query_terms": query_terms}
                )
        return sorted(ranked, key=lambda item: item["keyword_score"], reverse=True)

    def _semantic_rank(self, chunks: list[dict], query: str, query_terms: list[str]) -> list[dict]:
        query_vector = self._char_vector(query)
        if not query_vector:
            return []

        ranked = []
        for chunk in chunks:
            text = f"{chunk['title']} {chunk['section']} {chunk['chunk_text']}"
            score = self._cosine(query_vector, self._char_vector(text))
            if score > 0:
                ranked.append(
                    {**chunk, "semantic_score": round(score, 4), "rank_source": "local_semantic", "query_terms": query_terms}
                )
        return sorted(ranked, key=lambda item: item["semantic_score"], reverse=True)

    def _metadata_rank(self, chunks: list[dict], query: str, query_terms: list[str]) -> list[dict]:
        query_lower = query.lower()
        ranked = []
        for chunk in chunks:
            title = chunk["title"].lower()
            tags = [tag.lower() for tag in chunk["tags"]]
            department = str(chunk.get("department", "")).lower()
            score = 0.0
            if title and title in query_lower:
                score += 3.0
            score += sum(1.0 for term in query_terms if term in title)
            score += sum(0.8 for tag in tags if tag and tag in query_lower)
            if department and department in query_lower:
                score += 0.6
            score += min(chunk.get("reads", 0) / 1000, 0.3)
            if score > 0:
                ranked.append(
                    {**chunk, "metadata_score": round(score, 4), "rank_source": "metadata", "query_terms": query_terms}
                )
        return sorted(ranked, key=lambda item: item["metadata_score"], reverse=True)

    def _format_hit(self, item: dict) -> dict:
        snippet = self._snippet(item["chunk_text"], item.get("query_terms", []))
        section = item["section"]
        citation = f"{item['title']} v{item['version']}#{section}/chunk-{item['chunk_index'] + 1}"
        raw_scores = {
            "keyword": item.get("keyword_score", 0.0),
            "semantic": item.get("semantic_score", 0.0),
            "metadata": item.get("metadata_score", 0.0),
        }
        return {
            "document_id": item["id"],
            "chunk_id": item["chunk_id"],
            "chunk_index": item["chunk_index"],
            "title": item["title"],
            "section": section,
            "snippet": snippet,
            "score": round(item["score"], 4),
            "rrf_score": round(item["score"], 4),
            "raw_scores": raw_scores,
            "rank_sources": item.get("rank_sources", []),
            "retrieval_strategy": "chunked_hybrid_rrf",
            "citation": citation,
            "version": item["version"],
            "author": item["author"],
            "department": item["department"],
            "updated_at": item["updated_at"],
            "source": {
                "document_id": item["id"],
                "chunk_id": item["chunk_id"],
                "title": item["title"],
                "version": item["version"],
                "section": section,
                "chunk_index": item["chunk_index"],
                "author": item["author"],
                "department": item["department"],
                "updated_at": item["updated_at"],
                "snippet": snippet,
                "citation": citation,
                "retrieval_strategy": "chunked_hybrid_rrf",
                "raw_scores": raw_scores,
                "rank_sources": item.get("rank_sources", []),
            },
        }

    def _match_filters(self, doc: dict, filters: dict) -> bool:
        status = filters.get("status")
        if status and status != "all" and doc.get("status") != status:
            return False

        department_id = filters.get("department_id")
        if department_id and doc.get("department_id") != department_id:
            return False

        tag = filters.get("tag")
        if tag and tag not in doc.get("tags", []):
            return False

        return True

    def _snippet(self, text: str, terms: list[str], limit: int = 180) -> str:
        clean = " ".join(text.split())
        if len(clean) <= limit:
            return clean
        for term in terms:
            if len(term) < 2 and not re.match(r"[\u4e00-\u9fff]", term):
                continue
            index = clean.lower().find(term.lower())
            if index >= 0:
                start = max(0, index - limit // 3)
                end = min(len(clean), start + limit)
                prefix = "..." if start > 0 else ""
                suffix = "..." if end < len(clean) else ""
                return f"{prefix}{clean[start:end].strip()}{suffix}"
        return f"{clean[: limit - 3].rstrip()}..."

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]", text.lower())

    def _char_vector(self, text: str) -> Counter[str]:
        normalized = re.sub(r"\s+", "", text.lower())
        if not normalized:
            return Counter()
        grams = [normalized[index : index + 2] for index in range(max(len(normalized) - 1, 1))]
        return Counter(grams or [normalized])

    def _cosine(self, left: Counter[str], right: Counter[str]) -> float:
        if not left or not right:
            return 0.0
        numerator = sum(left[key] * right.get(key, 0) for key in left)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if not left_norm or not right_norm:
            return 0.0
        return numerator / (left_norm * right_norm)
