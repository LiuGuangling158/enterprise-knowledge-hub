import re


SENSITIVE_TERMS = ["工资单", "身份证", "银行卡", "商业秘密"]
SENSITIVE_PATTERNS = [
    ("手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("身份证号", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    ("访问密钥", re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[a-z0-9_\-]{8,}")),
]


def detect_sensitive_terms(content: str) -> list[dict]:
    findings = [{"term": term, "risk": "sensitive", "type": "keyword"} for term in SENSITIVE_TERMS if term in content]
    for name, pattern in SENSITIVE_PATTERNS:
        for match in pattern.finditer(content):
            findings.append(
                {
                    "term": name,
                    "risk": "sensitive",
                    "type": "pattern",
                    "sample": _mask(match.group(0)),
                }
            )
    return findings


def _mask(value: str) -> str:
    if len(value) <= 6:
        return "***"
    return f"{value[:3]}***{value[-3:]}"
