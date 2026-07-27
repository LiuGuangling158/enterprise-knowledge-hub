def split_markdown(text: str, max_chars: int = 700, overlap: int = 80) -> list[dict]:
    chunks: list[dict] = []
    cursor = 0
    index = 0
    while cursor < len(text):
        end = min(cursor + max_chars, len(text))
        chunks.append(
            {
                "chunk_index": index,
                "section": "正文",
                "text": text[cursor:end],
                "strategy": "recursive",
            }
        )
        index += 1
        cursor = max(end - overlap, end)
    return chunks
