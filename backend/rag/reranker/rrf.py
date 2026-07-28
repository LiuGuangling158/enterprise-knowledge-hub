def reciprocal_rank_fusion(rankings: list[list[dict]], k: int = 60) -> list[dict]:
    scores: dict[str, float] = {}
    payloads: dict[str, dict] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            key = item.get("chunk_id") or item["document_id"]
            scores[key] = scores.get(key, 0.0) + 1 / (k + rank)
            if key not in payloads:
                payloads[key] = {**item, "rank_sources": []}
            payloads[key].update(
                {
                    score_key: value
                    for score_key, value in item.items()
                    if score_key.endswith("_score") or score_key == "query_terms"
                }
            )
            if item.get("rank_source"):
                payloads[key]["rank_sources"].append(item["rank_source"])
    fused = [{**payloads[key], "score": round(score, 4)} for key, score in scores.items()]
    return sorted(fused, key=lambda item: item["score"], reverse=True)
