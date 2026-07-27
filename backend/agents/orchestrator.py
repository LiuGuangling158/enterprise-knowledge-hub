import asyncio
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

    async def stream_answer(self, question: str, scope: dict[str, str], session_id: str):
        trace_id = str(uuid4())
        route = self.router.classify(question)
        yield {"event": "agent_start", "data": {"trace_id": trace_id, "session_id": session_id, "agent": "router"}}
        await asyncio.sleep(0.05)
        yield {"event": "agent_result", "data": {"agent": "router", "intent": route["intent"], "confidence": route["confidence"]}}

        yield {"event": "tool_call", "data": {"agent": "retrieval", "tool": "hybrid_search", "args": {"query": question, "top_k": 5}}}
        result = self.retrieval.run(question, scope, top_k=5)
        await asyncio.sleep(0.05)
        yield {
            "event": "agent_result",
            "data": {
                "agent": "retrieval",
                "rewritten_query": result["rewritten_query"],
                "hit_count": len(result["results"]),
            },
        }

        qa_result = self.qa.answer(question, result["results"])
        for char in qa_result["answer"]:
            yield {"event": "answer_delta", "data": {"text": char}}
            await asyncio.sleep(0.005)

        save_meta = {
            "trace_id": trace_id,
            "confidence": qa_result["confidence"],
            "citations": qa_result["citations"],
            "rewritten_query": result["rewritten_query"],
            "hit_count": len(result["results"]),
        }
        self.document_service.save_qa_exchange(
            session_id=session_id,
            question=question,
            answer=qa_result["answer"],
            scope=scope,
            meta=save_meta,
        )
        yield {"event": "conversation_saved", "data": {"session_id": session_id}}
        yield {
            "event": "agent_complete",
            "data": {
                "trace_id": trace_id,
                "session_id": session_id,
                "confidence": qa_result["confidence"],
                "citations": qa_result["citations"],
            },
        }
