import asyncio
from time import perf_counter
from uuid import uuid4

from agents.qa_agent import QAAgent
from agents.retrieval_agent import RetrievalAgent
from agents.router_agent import RouterAgent
from rag.retrieval.hybrid import HybridRetriever
from services.document_service import DocumentService


class KnowledgeOrchestrator:
    def __init__(self, document_service: DocumentService) -> None:
        self.document_service = document_service
        retriever = HybridRetriever(document_service)
        self.router = RouterAgent()
        self.retrieval = RetrievalAgent(retriever)
        self.qa = QAAgent()

    def search(self, query: str, scope: dict[str, str], top_k: int = 5) -> dict:
        return self.retrieval.run(query, scope, top_k=top_k)

    def capabilities(self) -> dict:
        return {
            "agents": [
                {
                    "id": "router",
                    "name": "Router Agent",
                    "responsibility": "识别问题意图，规划后续执行路径",
                    "tools": [],
                },
                {
                    "id": "retrieval",
                    "name": "Retrieval Agent",
                    "responsibility": "执行 Query 改写、混合检索和证据召回",
                    "tools": ["hybrid_search"],
                },
                {
                    "id": "qa",
                    "name": "QA Agent",
                    "responsibility": "基于检索证据生成回答，并附带引用来源",
                    "tools": ["evidence_guard"],
                },
                {
                    "id": "memory",
                    "name": "Memory Agent",
                    "responsibility": "保存问答历史、引用来源和 Agent 轨迹",
                    "tools": ["conversation_store"],
                },
            ],
            "tools": [
                {"id": "hybrid_search", "name": "混合检索", "type": "retrieval"},
                {"id": "evidence_guard", "name": "证据置信度校验", "type": "guardrail"},
                {"id": "conversation_store", "name": "对话记忆", "type": "memory"},
            ],
        }

    async def stream_answer(self, question: str, scope: dict[str, str], session_id: str):
        trace_id = str(uuid4())
        started_at = perf_counter()
        trace_events = []

        def event(name: str, data: dict) -> dict:
            payload = {"event": name, "data": data}
            trace_events.append({"event": name, **data})
            return payload

        route = self.router.classify(question)
        question_preview = self._preview(question)
        yield event(
            "agent_start",
            {
                "trace_id": trace_id,
                "session_id": session_id,
                "agent": "router",
                "agent_name": "Router Agent",
                "stage": "intent_routing",
                "objective": "识别问题意图并选择执行路径",
                "input": question,
                "output": f"收到问题：{question_preview}",
            },
        )
        await asyncio.sleep(0.05)
        yield event(
            "agent_result",
            {
                "agent": "router",
                "agent_name": "Router Agent",
                "intent": route["intent"],
                "confidence": route["confidence"],
                "reason": route["reason"],
                "matched_keywords": route["matched_keywords"],
                "strategy": route["strategy"],
                "next_agents": ["retrieval", "qa", "memory"],
                "output": route["output"],
            },
        )
        yield event(
            "agent_plan",
            {
                "trace_id": trace_id,
                "intent": route["intent"],
                "strategy": route["strategy"],
                "steps": self._execution_plan(question, route),
                "output": f"为“{question_preview}”生成 {route['intent']} 执行计划。",
            },
        )

        yield event(
            "agent_start",
            {
                "trace_id": trace_id,
                "agent": "retrieval",
                "agent_name": "Retrieval Agent",
                "stage": "evidence_retrieval",
                "objective": "改写查询并召回可访问文档证据",
                "input": question,
                "output": f"准备检索与问题相关的文档证据：{question_preview}",
            },
        )
        yield event(
            "tool_call",
            {
                "agent": "retrieval",
                "agent_name": "Retrieval Agent",
                "tool": "hybrid_search",
                "args": {"query": question, "top_k": 5},
                "output": f"调用 hybrid_search，原始查询为“{question_preview}”，目标返回 Top 5 证据。",
            },
        )
        result = self.retrieval.run(question, scope, top_k=5)
        await asyncio.sleep(0.05)
        yield event(
            "tool_result",
            {
                "agent": "retrieval",
                "agent_name": "Retrieval Agent",
                "tool": "hybrid_search",
                "rewritten_query": result["rewritten_query"],
                "hit_count": len(result["results"]),
                "hits": self._summarize_hits(result["results"]),
                "output": self._retrieval_output(result),
            },
        )
        yield event(
            "agent_result",
            {
                "agent": "retrieval",
                "agent_name": "Retrieval Agent",
                "rewritten_query": result["rewritten_query"],
                "hit_count": len(result["results"]),
                "output": f"检索完成：Query 改写为“{result['rewritten_query']}”，召回 {len(result['results'])} 条候选证据。",
            },
        )

        yield event(
            "agent_start",
            {
                "trace_id": trace_id,
                "agent": "qa",
                "agent_name": "QA Agent",
                "stage": "grounded_answer",
                "objective": "基于证据生成可引用回答",
                "input": {
                    "question": question,
                    "evidence_count": len(result["results"]),
                },
                "output": f"开始根据 {len(result['results'])} 条证据组织回答。",
            },
        )
        yield event(
            "tool_call",
            {
                "agent": "qa",
                "agent_name": "QA Agent",
                "tool": "evidence_guard",
                "args": {"hit_count": len(result["results"])},
                "output": f"校验 {len(result['results'])} 条候选证据是否足以支撑回答。",
            },
        )
        qa_result = self.qa.answer(question, result["results"])
        yield event(
            "guardrail_result",
            {
                "agent": "qa",
                "agent_name": "QA Agent",
                "tool": "evidence_guard",
                "confidence": qa_result["confidence"],
                "citation_count": len(qa_result["citations"]),
                "output": f"证据校验完成：置信度 {qa_result['confidence']}，引用 {len(qa_result['citations'])} 个来源。",
            },
        )
        yield event(
            "agent_result",
            {
                "agent": "qa",
                "agent_name": "QA Agent",
                "answer_length": len(qa_result["answer"]),
                "citation_count": len(qa_result["citations"]),
                "confidence": qa_result["confidence"],
                "support_points": qa_result["support_points"],
                "answer_preview": self._preview(qa_result["answer"], 120),
                "output": qa_result["output"],
            },
        )
        for char in qa_result["answer"]:
            yield {"event": "answer_delta", "data": {"text": char}}
            await asyncio.sleep(0.005)

        duration_ms = int((perf_counter() - started_at) * 1000)
        run_summary = {
            "trace_id": trace_id,
            "intent": route["intent"],
            "duration_ms": duration_ms,
            "agent_count": 4,
            "tool_call_count": 3,
            "evidence_count": len(result["results"]),
            "confidence": qa_result["confidence"],
            "question": question,
            "strategy": route["strategy"],
            "top_citation": qa_result["citations"][0]["citation"] if qa_result["citations"] else None,
        }
        save_meta = {
            "trace_id": trace_id,
            "confidence": qa_result["confidence"],
            "citations": qa_result["citations"],
            "rewritten_query": result["rewritten_query"],
            "hit_count": len(result["results"]),
            "agent_trace": trace_events,
            "run_summary": run_summary,
        }
        yield event(
            "agent_start",
            {
                "trace_id": trace_id,
                "agent": "memory",
                "agent_name": "Memory Agent",
                "stage": "conversation_memory",
                "objective": "保存问答历史与执行轨迹",
                "input": {"session_id": session_id, "trace_id": trace_id},
                "output": f"准备把本轮问答写入会话 {session_id}。",
            },
        )
        yield event(
            "tool_call",
            {
                "agent": "memory",
                "agent_name": "Memory Agent",
                "tool": "conversation_store",
                "args": {"session_id": session_id},
                "output": f"调用 conversation_store，保存问题、回答、引用和 Agent 轨迹。",
            },
        )
        self.document_service.save_qa_exchange(
            session_id=session_id,
            question=question,
            answer=qa_result["answer"],
            scope=scope,
            meta=save_meta,
        )
        yield event("conversation_saved", {"session_id": session_id, "output": f"会话 {session_id} 已保存。"})
        yield event(
            "agent_result",
            {
                "agent": "memory",
                "agent_name": "Memory Agent",
                "session_id": session_id,
                "message_count": 2,
                "output": f"Memory Agent 已写入 2 条消息，并保存 {len(trace_events)} 条执行事件。",
            },
        )
        yield event(
            "agent_complete",
            {
                "trace_id": trace_id,
                "session_id": session_id,
                "confidence": qa_result["confidence"],
                "citations": qa_result["citations"],
                "run_summary": run_summary,
                "output": (
                    f"本轮 Agent 任务完成：意图 {route['intent']}，"
                    f"证据 {len(result['results'])} 条，引用 {len(qa_result['citations'])} 个。"
                ),
            },
        )

    def _execution_plan(self, question: str, route: dict) -> list[dict]:
        query_preview = self._preview(question, 42)
        return [
            {
                "agent": "router",
                "agent_name": "Router Agent",
                "objective": f"识别“{query_preview}”的问题意图",
                "output": route["output"],
                "status": "completed",
            },
            {
                "agent": "retrieval",
                "agent_name": "Retrieval Agent",
                "objective": f"按 {route['strategy']} 策略召回候选证据",
                "output": "等待检索工具返回本次命中文档。",
                "status": "pending",
            },
            {
                "agent": "qa",
                "agent_name": "QA Agent",
                "objective": "根据召回证据生成与问题对应的答案",
                "output": "等待证据校验和答案生成。",
                "status": "pending",
            },
            {
                "agent": "memory",
                "agent_name": "Memory Agent",
                "objective": f"保存会话 {self._preview(question, 24)} 的问答轨迹",
                "output": "等待最终回答完成后写入历史。",
                "status": "pending",
            },
        ]

    def _summarize_hits(self, hits: list[dict]) -> list[dict]:
        return [
            {
                "document_id": hit["document_id"],
                "title": hit["title"],
                "version": hit["version"],
                "section": hit["section"],
                "score": hit["score"],
                "citation": hit["citation"],
                "snippet": hit["snippet"],
            }
            for hit in hits[:5]
        ]

    def _retrieval_output(self, result: dict) -> str:
        hits = result["results"]
        if not hits:
            return f"Query 改写为“{result['rewritten_query']}”，未召回可访问证据。"

        top_hits = "；".join(
            f"{hit['title']} v{hit['version']}（{hit['score']}）"
            for hit in hits[:3]
        )
        return f"Query 改写为“{result['rewritten_query']}”，Top 命中：{top_hits}。"

    def _preview(self, text: str, limit: int = 80) -> str:
        clean = " ".join(text.split())
        if len(clean) <= limit:
            return clean
        return f"{clean[: limit - 3].rstrip()}..."
