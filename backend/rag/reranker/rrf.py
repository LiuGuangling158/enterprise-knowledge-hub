def reciprocal_rank_fusion(rankings: list[list[dict]], k: int = 60) -> list[dict]:
    scores: dict[str, float] = {}
    payloads: dict[str, dict] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            key = item["document_id"]
            scores[key] = scores.get(key, 0.0) + 1 / (k + rank)
            payloads[key] = item
    fused = [{**payloads[key], "score": round(score, 4)} for key, score in scores.items()]
    return sorted(fused, key=lambda item: item["score"], reverse=True)
