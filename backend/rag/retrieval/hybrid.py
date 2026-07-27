from rag.retrieval.query_rewriter import rewrite_query


class HybridRetriever:
    def __init__(self, document_service) -> None:
        self.document_service = document_service

    def search(self, query: str, scope: dict[str, str], top_k: int = 5) -> dict:
        rewritten = rewrite_query(query)
        terms = {term.lower() for term in rewritten.replace("，", " ").replace("。", " ").split() if term}
        candidates = []

        for doc in self.document_service.all_visible_text(scope):
            haystack = f"{doc['title']} {' '.join(doc['tags'])} {doc['content']}".lower()
            keyword_score = sum(1 for term in terms if term.lower() in haystack)
            semantic_score = self._semantic_overlap(rewritten, doc["content"])
            score = keyword_score * 0.55 + semantic_score * 0.45 + doc["reads"] / 1000
            if score > 0:
                candidates.append(
                    {
                        "document_id": doc["id"],
                        "title": doc["title"],
                        "section": "正文",
                        "snippet": doc["content"][:120],
                        "score": round(score, 3),
                        "citation": f"{doc['title']} v{doc['version']}#正文",
                    }
                )

        candidates.sort(key=lambda item: item["score"], reverse=True)
        return {"rewritten_query": rewritten, "results": candidates[:top_k]}

    def _semantic_overlap(self, query: str, content: str) -> float:
        query_chars = set(query)
        content_chars = set(content)
        if not query_chars:
            return 0.0
        return len(query_chars & content_chars) / len(query_chars)
