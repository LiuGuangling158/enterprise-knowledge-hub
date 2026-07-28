import json

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from agents.orchestrator import KnowledgeOrchestrator
from api.deps import CurrentUser, documents
from core.security import create_access_token
from models.schemas import (
    AdminUserUpdate,
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
    documents.record_operation(
        user,
        "auth.login",
        "user",
        user["id"],
        "用户登录",
        {"email": payload.email},
    )
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


@router.post("/documents/upload")
async def upload_document(
    request: Request,
    user: CurrentUser,
    filename: str = Query(..., min_length=1, max_length=240),
    visibility: str = Query(default="department"),
    tags: str = Query(default=""),
    department_id: str | None = Query(default=None),
    file: bytes = Body(..., media_type="application/octet-stream"),
) -> dict:
    return documents.upload_document(
        filename=filename,
        content_type=request.headers.get("content-type"),
        data=file,
        visibility=visibility,
        tags=tags,
        department_id=department_id,
        scope=user,
    )


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


@router.get("/documents/{document_id}/sensitive-scans")
async def list_sensitive_scans(document_id: str, user: CurrentUser) -> list[dict]:
    return documents.list_sensitive_scans(document_id, user)


@router.post("/documents/{document_id}/sensitive-scan")
async def run_sensitive_scan(document_id: str, user: CurrentUser) -> dict:
    return documents.run_sensitive_scan(document_id, user)


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


@router.get("/admin/overview")
async def admin_overview(user: CurrentUser) -> dict:
    return documents.admin_overview(user)


@router.get("/admin/users")
async def admin_users(user: CurrentUser) -> list[dict]:
    return documents.admin_users(user)


@router.patch("/admin/users/{user_id}")
async def admin_update_user(user_id: str, payload: AdminUserUpdate, user: CurrentUser) -> dict:
    return documents.admin_update_user(user_id, payload, user)


@router.get("/admin/departments")
async def admin_departments(user: CurrentUser) -> list[dict]:
    return documents.admin_departments(user)


@router.get("/admin/documents")
async def admin_documents(
    user: CurrentUser,
    status: str | None = None,
    department_id: str | None = None,
) -> list[dict]:
    return documents.admin_documents(user, status=status, department_id=department_id)


@router.get("/admin/approvals")
async def admin_approvals(user: CurrentUser, status: str | None = None) -> list[dict]:
    return documents.admin_approvals(user, status=status)


@router.get("/admin/operation-logs")
async def admin_operation_logs(
    user: CurrentUser,
    action: str | None = None,
    resource_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[dict]:
    return documents.admin_operation_logs(user, action=action, resource_type=resource_type, limit=limit)


@router.get("/admin/sensitive-scans")
async def admin_sensitive_scans(
    user: CurrentUser,
    risk_level: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[dict]:
    return documents.admin_sensitive_scans(user, risk_level=risk_level, limit=limit)


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
    status: str | None = None,
    department_id: str | None = None,
    tag: str | None = None,
) -> SearchResponse:
    filters = {"status": status, "department_id": department_id, "tag": tag}
    filters = {key: value for key, value in filters.items() if value}
    results = orchestrator.search(q, user, top_k=top_k, filters=filters)
    return SearchResponse(
        query=q,
        rewritten_query=results["rewritten_query"],
        results=results["results"],
        retrieval_meta=results.get("retrieval_meta", {}),
    )


@router.post("/ask")
async def ask(payload: AskRequest, user: CurrentUser) -> StreamingResponse:
    async def event_stream():
        async for event in orchestrator.stream_answer(payload.question, user, payload.session_id):
            yield f"event: {event['event']}\n"
            yield f"data: {json.dumps(event['data'], ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
