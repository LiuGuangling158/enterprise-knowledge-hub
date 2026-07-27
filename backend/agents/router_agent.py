class RouterAgent:
    def classify(self, query: str) -> dict[str, str | float]:
        normalized = query.strip()
        if any(word in normalized for word in ["对比", "趋势", "分析"]):
            intent = "analysis"
        elif any(word in normalized for word in ["审核", "合规", "敏感"]):
            intent = "review"
        else:
            intent = "retrieval_qa"
        return {"intent": intent, "confidence": 0.86}
