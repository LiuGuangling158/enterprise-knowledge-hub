from skills.sensitive_detect import detect_sensitive_terms


class ReviewAgent:
    def review(self, content: str) -> dict:
        findings = detect_sensitive_terms(content)
        return {
            "status": "blocked" if findings else "passed",
            "findings": findings,
        }
