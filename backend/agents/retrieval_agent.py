from rag.retrieval.hybrid import HybridRetriever


class RetrievalAgent:
    def __init__(self, retriever: HybridRetriever) -> None:
        self.retriever = retriever

    def run(self, query: str, scope: dict[str, str], top_k: int = 5) -> dict:
        return self.retriever.search(query, scope, top_k=top_k)
