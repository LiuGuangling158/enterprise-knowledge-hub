def rewrite_query(query: str) -> str:
    normalized = " ".join(query.strip().split())
    if len(normalized) <= 4:
        return f"企业内部知识库中关于{normalized}的制度、流程和相关文档"
    if "Q2" in normalized and "2026" not in normalized:
        return normalized.replace("Q2", "2026 年第二季度")
    return normalized
