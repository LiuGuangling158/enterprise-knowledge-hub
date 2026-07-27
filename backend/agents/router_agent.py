class RouterAgent:
    def classify(self, query: str) -> dict[str, str | float]:
        normalized = query.strip()
        if any(word in normalized for word in ["对比", "趋势", "分析"]):
            intent = "analysis"
            reason = "问题包含分析或对比意图，优先召回多篇文档作为证据。"
        elif any(word in normalized for word in ["审核", "合规", "敏感"]):
            intent = "review"
            reason = "问题包含审核、合规或敏感信息线索，需要保留证据来源。"
        else:
            intent = "retrieval_qa"
            reason = "问题适合通过知识库检索后生成可引用回答。"
        return {"intent": intent, "confidence": 0.86, "reason": reason}
