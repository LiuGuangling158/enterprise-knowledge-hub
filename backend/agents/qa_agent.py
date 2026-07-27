from rag.hallucination.guard import EvidenceGuard


class QAAgent:
    def __init__(self) -> None:
        self.guard = EvidenceGuard()

    def answer(self, question: str, hits: list[dict]) -> dict:
        if not hits:
            return {
                "answer": "未找到足够相关的内部文档。建议调整关键词，或联系文档负责人补充资料。",
                "citations": [],
                "confidence": "low",
            }

        facts = [hit["snippet"] for hit in hits[:3]]
        answer = "根据已发布或可访问的内部文档，" + "；".join(facts)
        citations = [{"title": hit["title"], "citation": hit["citation"]} for hit in hits[:3]]
        confidence = self.guard.confidence(answer, hits)
        return {"answer": answer, "citations": citations, "confidence": confidence}
