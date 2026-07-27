TOOL_REGISTRY = {
    "knowledge_db.search": {
        "description": "搜索当前用户可访问的知识库文档",
        "schema": {"query": "str", "top_k": "int", "filters": "dict"},
        "auth": "x-api-key",
        "rate_limit": "60 req/min",
    }
}
