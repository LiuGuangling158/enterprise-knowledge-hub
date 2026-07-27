import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from agents.orchestrator import KnowledgeOrchestrator
from api.deps import CurrentUser, documents
from core.security import create_access_token
from models.schemas import (
    AskRequest,
    CommentCreate,
    ConversationSessionOut,
    DocumentCreate,
    DocumentUpdate,
    LoginRequest,
    RegisterRequest,
    ReviewRequest,
    SearchResponse,
    SubmitRequest,
    TokenResponse,
    UserOut,
    VersionCompareResponse,
)


router = APIRouter()
orchestrator = KnowledgeOrchestrator(documents)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    user = documents.authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    return TokenResponse(access_token=create_access_token(user["id"]), user=UserOut(**user))


@router.post("/auth/register", response_model=TokenResponse)
async def register(payload: RegisterRequest) -> TokenResponse:
    user = documents.register_user(payload)
    return TokenResponse(access_token=create_access_token(user["id"]), user=UserOut(**user))


@router.get("/auth/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut(**user)


@router.get("/documents")
async def list_documents(
    user: CurrentUser,
    status: str | None = None,
    tag: str | None = None,
) -> list[dict]:
    return documents.list_documents(user, status=status, tag=tag)


@router.post("/documents")
async def create_document(payload: DocumentCreate, user: CurrentUser) -> dict:
    return documents.create_document(payload, user)


@router.get("/documents/{document_id}")
async def get_document(document_id: str, user: CurrentUser) -> dict:
    return documents.get_document(document_id, user)


@router.put("/documents/{document_id}")
async def update_document(document_id: str, payload: DocumentUpdate, user: CurrentUser) -> dict:
    return documents.update_document(document_id, payload, user)


@router.post("/documents/{document_id}/archive")
async def archive_document(document_id: str, user: CurrentUser) -> dict:
    return documents.archive_document(document_id, user)


@router.post("/documents/{document_id}/restore")
async def restore_document(document_id: str, user: CurrentUser) -> dict:
    return documents.restore_document(document_id, user)


@router.post("/documents/{document_id}/submit")
async def submit_document(document_id: str, payload: SubmitRequest, user: CurrentUser) -> dict:
    return documents.submit_document(document_id, payload, user)


@router.get("/documents/{document_id}/versions/compare", response_model=VersionCompareResponse)
async def compare_versions(
    document_id: str,
    user: CurrentUser,
    left: int = Query(..., ge=1),
    right: int = Query(..., ge=1),
) -> dict:
    return documents.compare_versions(document_id, left, right, user)


@router.get("/documents/{document_id}/versions")
async def list_versions(document_id: str, user: CurrentUser) -> list[dict]:
    return documents.list_versions(document_id, user)


@router.get("/documents/{document_id}/approvals")
async def list_document_approvals(document_id: str, user: CurrentUser) -> list[dict]:
    return documents.list_document_approvals(document_id, user)


@router.get("/documents/{document_id}/comments")
async def list_document_comments(document_id: str, user: CurrentUser) -> list[dict]:
    return documents.list_document_comments(document_id, user)


@router.post("/documents/{document_id}/comments")
async def add_document_comment(document_id: str, payload: CommentCreate, user: CurrentUser) -> dict:
    return documents.add_document_comment(document_id, payload, user)


@router.get("/approvals")
async def list_approvals(user: CurrentUser) -> list[dict]:
    return documents.list_approvals(user)


@router.post("/approvals/{approval_id}/review")
async def review_approval(approval_id: str, payload: ReviewRequest, user: CurrentUser) -> dict:
    return documents.review_approval(approval_id, payload, user)


@router.get("/metrics")
async def metrics(user: CurrentUser) -> dict:
    return documents.metrics(user)


@router.get("/conversations", response_model=list[ConversationSessionOut])
async def list_conversations(user: CurrentUser) -> list[dict]:
    return documents.list_conversations(user)


@router.get("/conversations/{session_id}", response_model=ConversationSessionOut)
async def get_conversation(session_id: str, user: CurrentUser) -> dict:
    return documents.get_conversation(session_id, user)


@router.get("/agents/capabilities")
async def agent_capabilities(user: CurrentUser) -> dict:
    return orchestrator.capabilities()


@router.get("/search", response_model=SearchResponse)
async def search(
    user: CurrentUser,
    q: str = Query(..., min_length=1),
    top_k: int = Query(default=5, ge=1, le=20),
) -> SearchResponse:
    results = orchestrator.search(q, user, top_k=top_k)
    return SearchResponse(query=q, rewritten_query=results["rewritten_query"], results=results["results"])


@router.post("/ask")
async def ask(payload: AskRequest, user: CurrentUser) -> StreamingResponse:
    async def event_stream():
        async for event in orchestrator.stream_answer(payload.question, user, payload.session_id):
            yield f"event: {event['event']}\n"
            yield f"data: {json.dumps(event['data'], ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
