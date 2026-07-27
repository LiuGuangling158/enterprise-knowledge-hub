class EmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text) % 17), float(sum(map(ord, text[:20])) % 31)] for text in texts]
