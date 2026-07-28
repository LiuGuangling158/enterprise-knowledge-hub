from rag.hallucination.guard import EvidenceGuard


class QAAgent:
    def __init__(self) -> None:
        self.guard = EvidenceGuard()

    def answer(self, question: str, hits: list[dict]) -> dict:
        if not hits:
            return {
                "answer": f"针对“{question}”，未找到足够相关的内部文档。建议调整关键词，或联系文档负责人补充资料。",
                "citations": [],
                "confidence": "low",
                "support_points": [],
                "output": "未召回可用证据，无法生成有引用支撑的答案。",
            }

        support_points = [
            f"{hit['title']} v{hit['version']}：{hit['snippet']}"
            for hit in hits[:3]
        ]
        answer = (
            f"针对“{question}”，我检索到 {len(hits)} 条可访问证据。"
            f"主要结论：{'；'.join(support_points)}"
        )
        citations = [
            {
                "document_id": hit["document_id"],
                "title": hit["title"],
                "citation": hit["citation"],
                "section": hit["section"],
                "snippet": hit["snippet"],
                "score": hit["score"],
                "version": hit["version"],
                "author": hit["author"],
                "department": hit["department"],
                "updated_at": hit["updated_at"],
                "source": hit["source"],
            }
            for hit in hits[:3]
        ]
        confidence = self.guard.confidence(answer, hits)
        return {
            "answer": answer,
            "citations": citations,
            "confidence": confidence,
            "support_points": support_points,
            "output": f"生成 {len(answer)} 字回答，采用 {len(citations)} 个引用来源，置信度 {confidence}。",
        }
