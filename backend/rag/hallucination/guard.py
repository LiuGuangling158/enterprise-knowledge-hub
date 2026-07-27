class EvidenceGuard:
    def confidence(self, answer: str, hits: list[dict]) -> str:
        if not hits:
            return "low"
        if len(hits) >= 2 and all(hit.get("citation") for hit in hits[:2]):
            return "high"
        return "medium"
