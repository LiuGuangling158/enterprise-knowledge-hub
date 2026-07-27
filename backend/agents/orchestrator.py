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
            trace_events.append(payload)
            return payload

        route = self.router.classify(question)
        yield event(
            "agent_start",
            {
                "trace_id": trace_id,
                "session_id": session_id,
                "agent": "router",
                "agent_name": "Router Agent",
                "stage": "intent_routing",
                "objective": "识别问题意图并选择执行路径",
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
                "next_agents": ["retrieval", "qa", "memory"],
            },
        )
        yield event(
            "agent_plan",
            {
                "trace_id": trace_id,
                "intent": route["intent"],
                "steps": self._execution_plan(route["intent"]),
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
            },
        )
        yield event(
            "tool_call",
            {
                "agent": "retrieval",
                "agent_name": "Retrieval Agent",
                "tool": "hybrid_search",
                "args": {"query": question, "top_k": 5},
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
            },
        )
        yield event(
            "agent_result",
            {
                "agent": "retrieval",
                "agent_name": "Retrieval Agent",
                "rewritten_query": result["rewritten_query"],
                "hit_count": len(result["results"]),
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
            },
        )
        yield event(
            "tool_call",
            {
                "agent": "qa",
                "agent_name": "QA Agent",
                "tool": "evidence_guard",
                "args": {"hit_count": len(result["results"])},
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
            },
        )
        yield event(
            "tool_call",
            {
                "agent": "memory",
                "agent_name": "Memory Agent",
                "tool": "conversation_store",
                "args": {"session_id": session_id},
            },
        )
        self.document_service.save_qa_exchange(
            session_id=session_id,
            question=question,
            answer=qa_result["answer"],
            scope=scope,
            meta=save_meta,
        )
        yield event("conversation_saved", {"session_id": session_id})
        yield event(
            "agent_result",
            {
                "agent": "memory",
                "agent_name": "Memory Agent",
                "session_id": session_id,
                "message_count": 2,
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
            },
        )

    def _execution_plan(self, intent: str) -> list[dict]:
        return [
            {
                "agent": "router",
                "agent_name": "Router Agent",
                "objective": f"识别意图：{intent}",
                "status": "completed",
            },
            {
                "agent": "retrieval",
                "agent_name": "Retrieval Agent",
                "objective": "调用混合检索工具召回候选证据",
                "status": "pending",
            },
            {
                "agent": "qa",
                "agent_name": "QA Agent",
                "objective": "生成带引用的答案并进行证据置信度校验",
                "status": "pending",
            },
            {
                "agent": "memory",
                "agent_name": "Memory Agent",
                "objective": "保存对话、引用和 Agent 轨迹",
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
