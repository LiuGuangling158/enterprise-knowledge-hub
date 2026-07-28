def split_markdown(text: str, max_chars: int = 700, overlap: int = 80) -> list[dict]:
    chunks: list[dict] = []
    clean = text.strip()
    if not clean:
        return chunks

    sections = _split_sections(clean)
    index = 0
    for section, body in sections:
        cursor = 0
        while cursor < len(body):
            end = min(cursor + max_chars, len(body))
            chunk_text = body[cursor:end].strip()
            if chunk_text:
                chunks.append(
                    {
                        "chunk_index": index,
                        "section": section,
                        "text": chunk_text,
                        "strategy": "recursive",
                    }
                )
                index += 1
            if end >= len(body):
                break
            next_cursor = max(0, end - overlap)
            cursor = next_cursor if next_cursor > cursor else end
    return chunks


def _split_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current_section = "正文"
    current_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip() or "正文"
            if current_lines:
                sections.append((current_section, current_lines))
                current_lines = []
            current_section = heading[:80]
            current_lines.append(line)
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_section, current_lines))

    return [(section, "\n".join(lines).strip()) for section, lines in sections if "\n".join(lines).strip()]
