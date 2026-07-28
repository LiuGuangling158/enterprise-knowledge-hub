class RouterAgent:
    def classify(self, query: str) -> dict:
        normalized = query.strip()
        analysis_keywords = [word for word in ["对比", "趋势", "分析", "差异", "比较"] if word in normalized]
        review_keywords = [word for word in ["审核", "合规", "敏感", "风险", "权限"] if word in normalized]

        if analysis_keywords:
            intent = "analysis"
            matched_keywords = analysis_keywords
            reason = "问题包含分析或对比意图，优先召回多篇文档作为证据。"
            strategy = "multi_document_analysis"
        elif review_keywords:
            intent = "review"
            matched_keywords = review_keywords
            reason = "问题包含审核、合规或敏感信息线索，需要保留证据来源。"
            strategy = "evidence_first_review"
        else:
            intent = "retrieval_qa"
            matched_keywords = []
            reason = "问题适合通过知识库检索后生成可引用回答。"
            strategy = "grounded_retrieval_qa"

        output = f"识别为 {intent}，策略为 {strategy}。"
        if matched_keywords:
            output += f" 命中关键词：{'、'.join(matched_keywords)}。"
        else:
            output += " 未命中特殊路由关键词，按通用知识问答处理。"
        return {
            "intent": intent,
            "confidence": 0.86,
            "reason": reason,
            "matched_keywords": matched_keywords,
            "strategy": strategy,
            "output": output,
        }
