def summarize_document(content: str, max_chars: int = 120) -> str:
    normalized = " ".join(content.split())
    return normalized[:max_chars]
