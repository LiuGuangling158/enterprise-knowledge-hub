def compare_documents(left: dict, right: dict) -> dict:
    return {
        "left": left.get("title"),
        "right": right.get("title"),
        "common_tags": sorted(set(left.get("tags", [])) & set(right.get("tags", []))),
    }
