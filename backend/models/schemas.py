from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=1, max_length=120)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=6, max_length=120)
    department_id: str = "dept-product"


class UserOut(BaseModel):
    id: str
    tenant_id: str
    department_id: str
    department: str
    email: str
    name: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    visibility: Literal["department", "public"] = "department"
    department_id: str | None = None


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    content: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None
    visibility: Literal["department", "public"] | None = None
    department_id: str | None = None
    summary: str | None = None


class SubmitRequest(BaseModel):
    summary: str = Field(min_length=1, max_length=1000)


class ReviewRequest(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    reason: str | None = Field(default=None, max_length=1000)


class AdminUserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    role: Literal["admin", "editor", "member"] | None = None
    department_id: str | None = None


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    session_id: str = Field(default="demo-session", min_length=1, max_length=64)


class ConversationMessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    meta: dict
    created_at: str


class ConversationSessionOut(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[ConversationMessageOut] = Field(default_factory=list)


class SearchHit(BaseModel):
    document_id: str
    title: str
    section: str
    snippet: str
    score: float
    citation: str
    version: int
    author: str
    department: str
    updated_at: str
    source: dict


class SearchResponse(BaseModel):
    query: str
    rewritten_query: str
    results: list[SearchHit]


class VersionCompareResponse(BaseModel):
    document_id: str
    left_version: int
    right_version: int
    left_title: str
    right_title: str
    summary: str
    added_lines: int
    removed_lines: int
    diff: list[str]
