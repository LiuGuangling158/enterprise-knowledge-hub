SENSITIVE_TERMS = ["工资单", "身份证", "银行卡", "商业秘密"]


def detect_sensitive_terms(content: str) -> list[dict]:
    return [{"term": term, "risk": "sensitive"} for term in SENSITIVE_TERMS if term in content]
