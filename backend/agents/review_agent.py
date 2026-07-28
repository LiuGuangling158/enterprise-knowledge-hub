import re
from datetime import datetime, timezone

from skills.sensitive_detect import detect_sensitive_terms


class ReviewAgent:
    def review(self, *, title: str, content: str, tags: list[str], related_documents: list[dict] | None = None) -> dict:
        findings = []
        findings.extend(self._format_findings(title, content, tags))
        findings.extend(self._sensitive_findings(content))
        findings.extend(self._duplicate_findings(title, content, related_documents or []))

        risk_level = self._risk_level(findings)
        status = "needs_attention" if risk_level in {"medium", "high"} else "passed"
        return {
            "agent": "Review Agent",
            "status": status,
            "risk_level": risk_level,
            "finding_count": len(findings),
            "findings": findings,
            "summary": self._summary(status, findings),
            "suggestions": self._suggestions(findings),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def _format_findings(self, title: str, content: str, tags: list[str]) -> list[dict]:
        findings = []
        if len(title.strip()) < 4:
            findings.append(
                {
                    "type": "format",
                    "severity": "low",
                    "message": "标题过短，建议补充业务对象或流程名称。",
                }
            )
        if len(content.strip()) < 30:
            findings.append(
                {
                    "type": "format",
                    "severity": "medium",
                    "message": "正文内容较短，可能缺少背景、流程或验收信息。",
                }
            )
        if not tags:
            findings.append(
                {
                    "type": "format",
                    "severity": "low",
                    "message": "未设置标签，后续检索和知识归类会变弱。",
                }
            )
        if "TODO" in content.upper() or "待补充" in content:
            findings.append(
                {
                    "type": "format",
                    "severity": "medium",
                    "message": "正文包含待补充内容，建议发布前完善。",
                }
            )
        return findings

    def _sensitive_findings(self, content: str) -> list[dict]:
        return [
            {
                "type": "sensitive",
                "severity": "high",
                "message": f"检测到疑似敏感信息：{item['term']}",
                "term": item["term"],
                "sample": item.get("sample"),
            }
            for item in detect_sensitive_terms(content)
        ]

    def _duplicate_findings(self, title: str, content: str, related_documents: list[dict]) -> list[dict]:
        findings = []
        normalized_title = self._normalize(title)
        content_terms = set(self._terms(content))
        for document in related_documents:
            title_match = self._normalize(document["title"]) == normalized_title
            other_terms = set(self._terms(document["content"]))
            overlap = len(content_terms & other_terms) / max(len(content_terms), 1)
            if title_match or (len(content_terms) >= 12 and overlap >= 0.72):
                findings.append(
                    {
                        "type": "duplicate",
                        "severity": "medium",
                        "message": f"疑似与《{document['title']}》内容重复。",
                        "document_id": document["id"],
                        "title": document["title"],
                        "overlap": round(overlap, 2),
                    }
                )
        return findings[:3]

    def _risk_level(self, findings: list[dict]) -> str:
        severities = {item.get("severity") for item in findings}
        if "high" in severities:
            return "high"
        if "medium" in severities:
            return "medium"
        if "low" in severities:
            return "low"
        return "none"

    def _summary(self, status: str, findings: list[dict]) -> str:
        if not findings:
            return "审核 Agent 未发现明显格式、重复或敏感信息风险。"
        high = len([item for item in findings if item.get("severity") == "high"])
        medium = len([item for item in findings if item.get("severity") == "medium"])
        low = len([item for item in findings if item.get("severity") == "low"])
        action = "建议人工重点复核" if status == "needs_attention" else "可进入常规人工审批"
        return f"审核 Agent 发现 {len(findings)} 项风险：高 {high}，中 {medium}，低 {low}。{action}。"

    def _suggestions(self, findings: list[dict]) -> list[str]:
        suggestions = []
        if any(item.get("type") == "sensitive" for item in findings):
            suggestions.append("发布前脱敏手机号、身份证、密钥、银行卡或商业秘密等内容。")
        if any(item.get("type") == "duplicate" for item in findings):
            suggestions.append("与相似文档合并或在摘要中说明差异，避免知识库重复。")
        if any(item.get("type") == "format" for item in findings):
            suggestions.append("补齐标题、标签、背景、流程、责任人或验收标准。")
        return suggestions or ["人工审批可继续按常规流程处理。"]

    def _normalize(self, value: str) -> str:
        return re.sub(r"\s+", "", value).lower()

    def _terms(self, value: str) -> list[str]:
        terms = re.findall(r"[a-zA-Z0-9]+", value.lower())
        for segment in re.findall(r"[\u4e00-\u9fff]+", value):
            if len(segment) == 1:
                terms.append(segment)
            else:
                terms.extend(segment[index : index + 2] for index in range(len(segment) - 1))
        return terms
