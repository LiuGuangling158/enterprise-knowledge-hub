import json
import re
from difflib import unified_diff
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from agents.review_agent import ReviewAgent
from core.config import settings
from core.security import hash_password, verify_password
from database.models import (
    Approval,
    ConversationMessage,
    ConversationSession,
    Department,
    Document,
    DocumentComment,
    DocumentUpload,
    DocumentVersion,
    OperationLog,
    SensitiveScan,
    User,
)
from database.session import SessionLocal
from skills.sensitive_detect import detect_sensitive_terms


SUPPORTED_UPLOAD_SUFFIXES = {".md": "markdown", ".markdown": "markdown", ".txt": "plain_text"}
DOCUMENT_STATUSES = {"all", "draft", "reviewing", "published", "rejected", "archived"}
APPROVAL_STATUSES = {"all", "pending", "approved", "rejected"}
SENSITIVE_RISK_LEVELS = {"all", "none", "low", "medium", "high"}


class DocumentService:
    def __init__(self) -> None:
        self.review_agent = ReviewAgent()

    def register_user(self, payload) -> dict:
        with SessionLocal() as db:
            existing = db.scalar(select(User).where(User.email == payload.email))
            if existing:
                raise HTTPException(status_code=409, detail="邮箱已注册")

            department = db.get(Department, payload.department_id)
            if not department or department.tenant_id != settings.demo_tenant_id:
                raise HTTPException(status_code=400, detail="部门不存在")

            user = User(
                id=self._new_id("user"),
                tenant_id=settings.demo_tenant_id,
                department_id=payload.department_id,
                email=payload.email,
                name=payload.name,
                role="member",
                password_hash=hash_password(payload.password),
            )
            db.add(user)
            db.flush()
            self._add_operation_log(
                db,
                {"tenant_id": user.tenant_id, "user_id": user.id},
                "auth.register",
                "user",
                user.id,
                "用户注册",
                {"email": user.email, "department_id": user.department_id},
            )
            db.commit()
            db.refresh(user)
            return self._user_to_dict(user)

    def authenticate_user(self, email: str, password: str) -> dict | None:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == email))
            if not user or not verify_password(password, user.password_hash):
                return None
            return self._user_to_dict(user)

    def record_operation(
        self,
        scope: dict[str, str],
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        summary: str = "",
        metadata: dict | None = None,
    ) -> None:
        with SessionLocal() as db:
            self._add_operation_log(db, scope, action, resource_type, resource_id, summary, metadata)
            db.commit()

    def get_user(self, user_id: str) -> dict | None:
        with SessionLocal() as db:
            user = db.get(User, user_id)
            return self._user_to_dict(user) if user else None

    def list_documents(self, scope: dict[str, str], status: str | None = None, tag: str | None = None) -> list[dict]:
        with SessionLocal() as db:
            statement = self._visible_documents_statement(scope)
            if status:
                statement = statement.where(Document.status == status)
            else:
                statement = statement.where(Document.status != "archived")
            statement = statement.order_by(Document.updated_at.desc())
            rows = db.scalars(statement).all()
            documents = [self._document_to_dict(row) for row in rows]
            if tag:
                documents = [row for row in documents if tag in row["tags"]]
            return documents

    def get_document(self, document_id: str, scope: dict[str, str]) -> dict:
        with SessionLocal() as db:
            doc = self._get_visible_document(db, document_id, scope)
            doc.reads += 1
            db.commit()
            db.refresh(doc)
            return self._document_to_dict(doc)

    def create_document(self, payload, scope: dict[str, str]) -> dict:
        with SessionLocal() as db:
            department_id = self._resolve_department_id(db, payload.department_id, scope)
            doc = Document(
                id=self._new_id("doc"),
                tenant_id=scope["tenant_id"],
                department_id=department_id,
                title=payload.title,
                content=payload.content,
                summary=self._summarize_document(payload.title, payload.content),
                author_id=scope["user_id"],
                status="draft",
                visibility=payload.visibility,
                version=1,
                tags_json=json.dumps(payload.tags, ensure_ascii=False),
            )
            db.add(doc)
            db.flush()
            self._add_version(db, doc, scope["user_id"], "创建文档")
            self._scan_document_for_sensitive(db, doc, scope["user_id"], "create")
            self._add_operation_log(
                db,
                scope,
                "document.create",
                "document",
                doc.id,
                "创建文档",
                {"title": doc.title, "visibility": doc.visibility, "department_id": doc.department_id},
            )
            db.commit()
            db.refresh(doc)
            return self._document_to_dict(doc)

    def upload_document(
        self,
        *,
        filename: str,
        content_type: str | None,
        data: bytes,
        visibility: str,
        tags: str,
        department_id: str | None,
        scope: dict[str, str],
    ) -> dict:
        if visibility not in {"department", "public"}:
            raise HTTPException(status_code=422, detail="可见范围只能是 department 或 public")
        if not data:
            raise HTTPException(status_code=400, detail="上传文件不能为空")
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="上传文件超过大小限制")

        original_filename = self._sanitize_filename(filename)
        suffix = Path(original_filename).suffix.lower()
        parser = SUPPORTED_UPLOAD_SUFFIXES.get(suffix)
        if not parser:
            raise HTTPException(status_code=415, detail="当前仅支持 Markdown 和文本文件上传")

        content = self._decode_uploaded_text(data)
        title = Path(original_filename).stem.strip() or "未命名上传文档"
        parsed_tags = self._parse_upload_tags(tags)

        with SessionLocal() as db:
            resolved_department_id = self._resolve_department_id(db, department_id, scope)
            doc = Document(
                id=self._new_id("doc"),
                tenant_id=scope["tenant_id"],
                department_id=resolved_department_id,
                title=title[:240],
                content=content,
                summary=self._summarize_document(title, content),
                author_id=scope["user_id"],
                status="draft",
                visibility=visibility,
                version=1,
                tags_json=json.dumps(parsed_tags, ensure_ascii=False),
            )
            db.add(doc)
            db.flush()

            stored_path = self._store_upload_file(
                tenant_id=scope["tenant_id"],
                document_id=doc.id,
                original_filename=original_filename,
                data=data,
            )
            upload = DocumentUpload(
                id=self._new_id("upl"),
                document_id=doc.id,
                tenant_id=scope["tenant_id"],
                department_id=resolved_department_id,
                uploader_id=scope["user_id"],
                original_filename=original_filename,
                stored_path=stored_path,
                content_type=content_type or "application/octet-stream",
                size_bytes=len(data),
                parser=parser,
                status="parsed",
            )
            db.add(upload)
            self._add_version(db, doc, scope["user_id"], f"上传解析：{original_filename}")
            self._scan_document_for_sensitive(db, doc, scope["user_id"], "upload")
            self._add_operation_log(
                db,
                scope,
                "document.upload",
                "document",
                doc.id,
                "上传文档并解析",
                {
                    "title": doc.title,
                    "upload_id": upload.id,
                    "filename": original_filename,
                    "size_bytes": len(data),
                    "parser": parser,
                },
            )
            db.commit()
            db.refresh(doc)
            return self._document_to_dict(doc)

    def update_document(self, document_id: str, payload, scope: dict[str, str]) -> dict:
        with SessionLocal() as db:
            doc = self._get_visible_document(db, document_id, scope)
            self._assert_can_edit(doc, scope)
            if doc.status == "reviewing":
                raise HTTPException(status_code=409, detail="审核中的文档不可编辑")
            if doc.status == "archived":
                raise HTTPException(status_code=409, detail="已归档的文档需要恢复后再编辑")

            changed = False
            regenerate_summary = False
            for field in ["title", "content", "visibility"]:
                value = getattr(payload, field)
                if value is not None and getattr(doc, field) != value:
                    setattr(doc, field, value)
                    changed = True
                    if field in {"title", "content"}:
                        regenerate_summary = True
            if payload.department_id is not None:
                department_id = self._resolve_department_id(db, payload.department_id, scope)
                if doc.department_id != department_id:
                    doc.department_id = department_id
                    changed = True
            if payload.tags is not None:
                doc.tags_json = json.dumps(payload.tags, ensure_ascii=False)
                changed = True

            if changed:
                if regenerate_summary or not doc.summary:
                    doc.summary = self._summarize_document(doc.title, doc.content)
                doc.version += 1
                doc.status = "draft"
                doc.updated_at = datetime.now(timezone.utc)
                self._add_version(db, doc, scope["user_id"], payload.summary or "保存文档")
                self._scan_document_for_sensitive(db, doc, scope["user_id"], "update")
                self._add_operation_log(
                    db,
                    scope,
                    "document.update",
                    "document",
                    doc.id,
                    payload.summary or "更新文档",
                    {"title": doc.title, "version": doc.version, "status": doc.status},
                )
            db.commit()
            db.refresh(doc)
            return self._document_to_dict(doc)

    def archive_document(self, document_id: str, scope: dict[str, str]) -> dict:
        with SessionLocal() as db:
            doc = self._get_visible_document(db, document_id, scope)
            self._assert_can_edit(doc, scope)
            if doc.status == "reviewing":
                raise HTTPException(status_code=409, detail="审核中的文档不可归档")

            doc.status = "archived"
            doc.updated_at = datetime.now(timezone.utc)
            self._add_operation_log(
                db,
                scope,
                "document.archive",
                "document",
                doc.id,
                "归档文档",
                {"title": doc.title, "version": doc.version},
            )
            db.commit()
            db.refresh(doc)
            return self._document_to_dict(doc)

    def restore_document(self, document_id: str, scope: dict[str, str]) -> dict:
        with SessionLocal() as db:
            doc = self._get_visible_document(db, document_id, scope)
            self._assert_can_edit(doc, scope)
            if doc.status != "archived":
                return self._document_to_dict(doc)

            doc.status = "draft"
            doc.updated_at = datetime.now(timezone.utc)
            self._add_operation_log(
                db,
                scope,
                "document.restore",
                "document",
                doc.id,
                "恢复文档",
                {"title": doc.title, "version": doc.version},
            )
            db.commit()
            db.refresh(doc)
            return self._document_to_dict(doc)

    def submit_document(self, document_id: str, payload, scope: dict[str, str]) -> dict:
        with SessionLocal() as db:
            doc = self._get_visible_document(db, document_id, scope)
            self._assert_can_edit(doc, scope)
            if doc.status == "archived":
                raise HTTPException(status_code=409, detail="已归档的文档不可提交审批")
            existing = db.scalar(
                select(Approval).where(Approval.document_id == document_id, Approval.status == "pending")
            )
            if existing:
                raise HTTPException(status_code=409, detail="该文档已有待审批记录")

            agent_review = self.review_agent.review(
                title=doc.title,
                content=doc.content,
                tags=json.loads(doc.tags_json or "[]"),
                related_documents=self._review_related_documents(db, doc),
            )
            self._scan_document_for_sensitive(db, doc, scope["user_id"], "submit")
            doc.status = "reviewing"
            doc.updated_at = datetime.now(timezone.utc)
            approval = Approval(
                id=self._new_id("approval"),
                document_id=doc.id,
                submitter_id=scope["user_id"],
                status="pending",
                summary=payload.summary,
                agent_review_json=json.dumps(agent_review, ensure_ascii=False),
            )
            db.add(approval)
            self._add_operation_log(
                db,
                scope,
                "approval.submit",
                "approval",
                approval.id,
                "提交发布审批",
                {
                    "document_id": doc.id,
                    "title": doc.title,
                    "agent_risk_level": agent_review.get("risk_level"),
                    "agent_finding_count": agent_review.get("finding_count"),
                },
            )
            try:
                db.commit()
            except IntegrityError as exc:
                db.rollback()
                raise HTTPException(status_code=409, detail="该文档已有待审批记录") from exc
            db.refresh(approval)
            return self._approval_to_dict(approval)

    def list_approvals(self, scope: dict[str, str]) -> list[dict]:
        with SessionLocal() as db:
            visible_ids = [
                doc.id
                for doc in db.scalars(
                    self._visible_documents_statement(scope).where(Document.status != "archived")
                ).all()
            ]
            if not visible_ids:
                return []
            rows = db.scalars(
                select(Approval)
                .options(
                    joinedload(Approval.document),
                    joinedload(Approval.submitter),
                    joinedload(Approval.reviewer),
                )
                .where(Approval.document_id.in_(visible_ids))
                .order_by(Approval.submitted_at.desc())
            ).all()
            return [self._approval_to_dict(row) for row in rows]

    def review_approval(self, approval_id: str, payload, scope: dict[str, str]) -> dict:
        if scope["role"] != "admin":
            raise HTTPException(status_code=403, detail="仅管理员可审批发布")

        with SessionLocal() as db:
            approval = db.scalar(
                select(Approval)
                .options(
                    joinedload(Approval.document),
                    joinedload(Approval.submitter),
                    joinedload(Approval.reviewer),
                )
                .where(Approval.id == approval_id)
            )
            if not approval:
                raise HTTPException(status_code=404, detail="审批记录不存在")
            if approval.status != "pending":
                raise HTTPException(status_code=409, detail="审批已处理")
            if approval.document.tenant_id != scope["tenant_id"]:
                raise HTTPException(status_code=403, detail="无权审批该文档")

            approval.reviewer_id = scope["user_id"]
            approval.reviewed_at = datetime.now(timezone.utc)
            approval.reason = payload.reason
            if payload.action == "approve":
                approval.status = "approved"
                approval.document.status = "published"
            else:
                approval.status = "rejected"
                approval.document.status = "rejected"
            approval.document.updated_at = datetime.now(timezone.utc)
            self._add_operation_log(
                db,
                scope,
                "approval.review",
                "approval",
                approval.id,
                "处理发布审批",
                {
                    "document_id": approval.document_id,
                    "action": payload.action,
                    "result": approval.status,
                    "reason": payload.reason,
                },
            )
            db.commit()
            db.refresh(approval)
            return self._approval_to_dict(approval)

    def list_versions(self, document_id: str, scope: dict[str, str]) -> list[dict]:
        with SessionLocal() as db:
            self._get_visible_document(db, document_id, scope)
            rows = db.scalars(
                select(DocumentVersion)
                .options(joinedload(DocumentVersion.creator))
                .where(DocumentVersion.document_id == document_id)
                .order_by(DocumentVersion.version.desc(), DocumentVersion.created_at.desc())
            ).all()
            return [self._version_to_dict(row) for row in rows]

    def compare_versions(self, document_id: str, left: int, right: int, scope: dict[str, str]) -> dict:
        with SessionLocal() as db:
            self._get_visible_document(db, document_id, scope)
            rows = db.scalars(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == document_id,
                    DocumentVersion.version.in_([left, right]),
                )
            ).all()
            by_version = {row.version: row for row in rows}
            if left not in by_version or right not in by_version:
                raise HTTPException(status_code=404, detail="版本不存在或无权访问")

            left_row = by_version[left]
            right_row = by_version[right]
            diff_lines = list(
                unified_diff(
                    left_row.content.splitlines(),
                    right_row.content.splitlines(),
                    fromfile=f"v{left}",
                    tofile=f"v{right}",
                    lineterm="",
                )
            )
            added_lines = len([line for line in diff_lines if line.startswith("+") and not line.startswith("+++")])
            removed_lines = len([line for line in diff_lines if line.startswith("-") and not line.startswith("---")])
            return {
                "document_id": document_id,
                "left_version": left,
                "right_version": right,
                "left_title": left_row.title,
                "right_title": right_row.title,
                "summary": f"v{left} 到 v{right}：新增 {added_lines} 行，删除 {removed_lines} 行",
                "added_lines": added_lines,
                "removed_lines": removed_lines,
                "diff": diff_lines,
            }

    def list_document_approvals(self, document_id: str, scope: dict[str, str]) -> list[dict]:
        with SessionLocal() as db:
            self._get_visible_document(db, document_id, scope)
            rows = db.scalars(
                select(Approval)
                .options(
                    joinedload(Approval.document),
                    joinedload(Approval.submitter),
                    joinedload(Approval.reviewer),
                )
                .where(Approval.document_id == document_id)
                .order_by(Approval.submitted_at.desc())
            ).all()
            return [self._approval_to_dict(row) for row in rows]

    def list_document_comments(self, document_id: str, scope: dict[str, str]) -> list[dict]:
        with SessionLocal() as db:
            self._get_visible_document(db, document_id, scope)
            rows = db.scalars(
                select(DocumentComment)
                .options(joinedload(DocumentComment.author))
                .where(DocumentComment.document_id == document_id)
                .order_by(DocumentComment.created_at.asc())
            ).all()
            return [self._comment_to_dict(row) for row in rows]

    def add_document_comment(self, document_id: str, payload, scope: dict[str, str]) -> dict:
        with SessionLocal() as db:
            doc = self._get_visible_document(db, document_id, scope)
            if doc.status == "archived":
                raise HTTPException(status_code=409, detail="已归档的文档不可继续评论")
            content = payload.content.strip()
            if not content:
                raise HTTPException(status_code=422, detail="评论内容不能为空")
            comment = DocumentComment(
                id=self._new_id("comment"),
                document_id=document_id,
                author_id=scope["user_id"],
                content=content,
            )
            db.add(comment)
            self._add_operation_log(
                db,
                scope,
                "comment.create",
                "comment",
                comment.id,
                "添加协作评论",
                {"document_id": doc.id, "title": doc.title},
            )
            db.commit()
            db.refresh(comment)
            return self._comment_to_dict(comment)

    def metrics(self, scope: dict[str, str]) -> dict:
        rows = self.list_documents(scope)
        since = datetime.now(timezone.utc) - timedelta(days=7)
        weekly_new = len([row for row in rows if self._parse_datetime(row["created_at"]) >= since])
        pending = len([item for item in self.list_approvals(scope) if item["status"] == "pending"])
        active_users = self._active_user_count(scope)
        return {
            "document_total": len(rows),
            "weekly_new": weekly_new,
            "active_users": active_users,
            "pending_approvals": pending,
            "trend": [
                {"day": "周一", "documents": 4, "reads": 86},
                {"day": "周二", "documents": 7, "reads": 104},
                {"day": "周三", "documents": 5, "reads": 93},
                {"day": "周四", "documents": 8, "reads": 121},
                {"day": "周五", "documents": 9, "reads": 138},
            ],
            "top_documents": sorted(rows, key=lambda row: row["reads"], reverse=True)[:5],
        }

    def admin_overview(self, scope: dict[str, str]) -> dict:
        self._assert_admin(scope)
        with SessionLocal() as db:
            users = db.scalars(
                select(User)
                .options(joinedload(User.department))
                .where(User.tenant_id == scope["tenant_id"])
                .order_by(User.created_at.desc())
            ).all()
            departments = db.scalars(
                select(Department)
                .where(Department.tenant_id == scope["tenant_id"])
                .order_by(Department.created_at.asc())
            ).all()
            documents = db.scalars(
                select(Document)
                .options(joinedload(Document.author), joinedload(Document.department))
                .where(Document.tenant_id == scope["tenant_id"])
                .order_by(Document.updated_at.desc())
            ).all()
            approvals = db.scalars(
                select(Approval)
                .join(Approval.document)
                .options(
                    joinedload(Approval.document),
                    joinedload(Approval.submitter),
                    joinedload(Approval.reviewer),
                )
                .where(Document.tenant_id == scope["tenant_id"])
                .order_by(Approval.submitted_at.desc())
            ).all()
            uploads = db.scalars(
                select(DocumentUpload)
                .options(
                    joinedload(DocumentUpload.document),
                    joinedload(DocumentUpload.department),
                    joinedload(DocumentUpload.uploader),
                )
                .where(DocumentUpload.tenant_id == scope["tenant_id"])
                .order_by(DocumentUpload.created_at.desc())
            ).all()
            operation_log_total = db.scalar(
                select(func.count()).select_from(OperationLog).where(OperationLog.tenant_id == scope["tenant_id"])
            ) or 0
            sensitive_scans = db.scalars(
                select(SensitiveScan).where(SensitiveScan.tenant_id == scope["tenant_id"])
            ).all()

            since = datetime.now(timezone.utc) - timedelta(days=7)
            status_counts = self._document_status_counts(documents)
            department_rows = [
                self._admin_department_to_dict(department, users, documents, approvals)
                for department in departments
            ]
            return {
                "metrics": {
                    "user_total": len(users),
                    "department_total": len(departments),
                    "document_total": len(documents),
                    "upload_total": len(uploads),
                    "pending_approvals": len([item for item in approvals if item.status == "pending"]),
                    "published_documents": status_counts.get("published", 0),
                    "archived_documents": status_counts.get("archived", 0),
                    "weekly_new_documents": len([doc for doc in documents if self._is_since(doc.created_at, since)]),
                    "weekly_uploads": len([upload for upload in uploads if self._is_since(upload.created_at, since)]),
                    "total_reads": sum(doc.reads for doc in documents),
                    "operation_log_total": operation_log_total,
                    "sensitive_risk_total": len(
                        [scan for scan in sensitive_scans if scan.status == "needs_attention"]
                    ),
                },
                "status_breakdown": [
                    {"status": status, "count": count}
                    for status, count in sorted(status_counts.items())
                ],
                "department_breakdown": department_rows,
                "recent_documents": [self._document_to_dict(doc) for doc in documents[:6]],
                "recent_approvals": [self._approval_to_dict(approval) for approval in approvals[:6]],
                "recent_uploads": [self._admin_upload_to_dict(upload) for upload in uploads[:6]],
            }

    def admin_users(self, scope: dict[str, str]) -> list[dict]:
        self._assert_admin(scope)
        with SessionLocal() as db:
            users = db.scalars(
                select(User)
                .options(joinedload(User.department))
                .where(User.tenant_id == scope["tenant_id"])
                .order_by(User.created_at.desc())
            ).all()
            documents = db.scalars(select(Document).where(Document.tenant_id == scope["tenant_id"])).all()
            approvals = db.scalars(
                select(Approval).join(Approval.document).where(Document.tenant_id == scope["tenant_id"])
            ).all()
            conversations = db.scalars(
                select(ConversationSession).where(ConversationSession.tenant_id == scope["tenant_id"])
            ).all()
            return [
                self._admin_user_to_dict(user, documents, approvals, conversations)
                for user in users
            ]

    def admin_departments(self, scope: dict[str, str]) -> list[dict]:
        self._assert_admin(scope)
        with SessionLocal() as db:
            departments = db.scalars(
                select(Department)
                .where(Department.tenant_id == scope["tenant_id"])
                .order_by(Department.created_at.asc())
            ).all()
            users = db.scalars(select(User).where(User.tenant_id == scope["tenant_id"])).all()
            documents = db.scalars(select(Document).where(Document.tenant_id == scope["tenant_id"])).all()
            approvals = db.scalars(
                select(Approval)
                .join(Approval.document)
                .options(joinedload(Approval.document))
                .where(Document.tenant_id == scope["tenant_id"])
            ).all()
            return [
                self._admin_department_to_dict(department, users, documents, approvals)
                for department in departments
            ]

    def admin_documents(
        self,
        scope: dict[str, str],
        status: str | None = None,
        department_id: str | None = None,
    ) -> list[dict]:
        self._assert_admin(scope)
        self._validate_status_filter(status, DOCUMENT_STATUSES, "文档状态")
        with SessionLocal() as db:
            statement = (
                select(Document)
                .options(joinedload(Document.author), joinedload(Document.department))
                .where(Document.tenant_id == scope["tenant_id"])
            )
            if status and status != "all":
                statement = statement.where(Document.status == status)
            if department_id:
                statement = statement.where(Document.department_id == department_id)
            rows = db.scalars(statement.order_by(Document.updated_at.desc())).all()
            return [self._document_to_dict(row) for row in rows]

    def admin_approvals(self, scope: dict[str, str], status: str | None = None) -> list[dict]:
        self._assert_admin(scope)
        self._validate_status_filter(status, APPROVAL_STATUSES, "审批状态")
        with SessionLocal() as db:
            statement = (
                select(Approval)
                .join(Approval.document)
                .options(
                    joinedload(Approval.document),
                    joinedload(Approval.submitter),
                    joinedload(Approval.reviewer),
                )
                .where(Document.tenant_id == scope["tenant_id"])
            )
            if status and status != "all":
                statement = statement.where(Approval.status == status)
            rows = db.scalars(statement.order_by(Approval.submitted_at.desc())).all()
            return [self._approval_to_dict(row) for row in rows]

    def list_sensitive_scans(self, document_id: str, scope: dict[str, str]) -> list[dict]:
        with SessionLocal() as db:
            self._get_visible_document(db, document_id, scope)
            rows = db.scalars(
                select(SensitiveScan)
                .options(joinedload(SensitiveScan.document), joinedload(SensitiveScan.scanner))
                .where(SensitiveScan.document_id == document_id, SensitiveScan.tenant_id == scope["tenant_id"])
                .order_by(SensitiveScan.created_at.desc())
            ).all()
            return [self._sensitive_scan_to_dict(row) for row in rows]

    def run_sensitive_scan(self, document_id: str, scope: dict[str, str]) -> dict:
        with SessionLocal() as db:
            doc = self._get_visible_document(db, document_id, scope)
            self._assert_can_edit(doc, scope)
            scan = self._scan_document_for_sensitive(db, doc, scope["user_id"], "manual")
            db.commit()
            db.refresh(scan)
            return self._sensitive_scan_to_dict(scan)

    def admin_sensitive_scans(
        self,
        scope: dict[str, str],
        risk_level: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        self._assert_admin(scope)
        self._validate_status_filter(risk_level, SENSITIVE_RISK_LEVELS, "风险等级")
        with SessionLocal() as db:
            statement = (
                select(SensitiveScan)
                .options(joinedload(SensitiveScan.document), joinedload(SensitiveScan.scanner))
                .where(SensitiveScan.tenant_id == scope["tenant_id"])
            )
            if risk_level and risk_level != "all":
                statement = statement.where(SensitiveScan.risk_level == risk_level)
            rows = db.scalars(statement.order_by(SensitiveScan.created_at.desc()).limit(self._safe_limit(limit))).all()
            return [self._sensitive_scan_to_dict(row) for row in rows]

    def admin_operation_logs(
        self,
        scope: dict[str, str],
        action: str | None = None,
        resource_type: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        self._assert_admin(scope)
        with SessionLocal() as db:
            statement = (
                select(OperationLog)
                .options(joinedload(OperationLog.actor))
                .where(OperationLog.tenant_id == scope["tenant_id"])
            )
            if action:
                statement = statement.where(OperationLog.action == action)
            if resource_type:
                statement = statement.where(OperationLog.resource_type == resource_type)
            rows = db.scalars(statement.order_by(OperationLog.created_at.desc()).limit(self._safe_limit(limit))).all()
            return [self._operation_log_to_dict(row) for row in rows]

    def admin_update_user(self, user_id: str, payload, scope: dict[str, str]) -> dict:
        self._assert_admin(scope)
        with SessionLocal() as db:
            user = db.scalar(
                select(User)
                .options(joinedload(User.department))
                .where(User.id == user_id, User.tenant_id == scope["tenant_id"])
            )
            if not user:
                raise HTTPException(status_code=404, detail="用户不存在")

            before = {
                "name": user.name,
                "role": user.role,
                "department_id": user.department_id,
            }

            if payload.department_id is not None:
                department = db.get(Department, payload.department_id)
                if not department or department.tenant_id != scope["tenant_id"]:
                    raise HTTPException(status_code=400, detail="部门不存在")
                user.department_id = payload.department_id

            if payload.name is not None:
                name = payload.name.strip()
                if not name:
                    raise HTTPException(status_code=422, detail="用户姓名不能为空")
                user.name = name

            if payload.role is not None and payload.role != user.role:
                if user.role == "admin" and payload.role != "admin":
                    admin_count = db.scalar(
                        select(func.count())
                        .select_from(User)
                        .where(User.tenant_id == scope["tenant_id"], User.role == "admin")
                    )
                    if admin_count <= 1:
                        raise HTTPException(status_code=409, detail="至少保留一名管理员")
                user.role = payload.role

            self._add_operation_log(
                db,
                scope,
                "admin.user.update",
                "user",
                user.id,
                "更新用户资料或权限",
                {
                    "before": before,
                    "after": {
                        "name": user.name,
                        "role": user.role,
                        "department_id": user.department_id,
                    },
                },
            )
            db.commit()
            db.refresh(user)
            documents = db.scalars(select(Document).where(Document.tenant_id == scope["tenant_id"])).all()
            approvals = db.scalars(
                select(Approval).join(Approval.document).where(Document.tenant_id == scope["tenant_id"])
            ).all()
            conversations = db.scalars(
                select(ConversationSession).where(ConversationSession.tenant_id == scope["tenant_id"])
            ).all()
            return self._admin_user_to_dict(user, documents, approvals, conversations)

    def all_visible_text(self, scope: dict[str, str]) -> list[dict]:
        return self.list_documents(scope)

    def list_conversations(self, scope: dict[str, str]) -> list[dict]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(ConversationSession)
                .where(
                    ConversationSession.tenant_id == scope["tenant_id"],
                    ConversationSession.user_id == scope["user_id"],
                )
                .order_by(ConversationSession.updated_at.desc())
            ).all()
            return [self._conversation_to_dict(row) for row in rows]

    def get_conversation(self, session_id: str, scope: dict[str, str]) -> dict:
        with SessionLocal() as db:
            session = self._get_owned_conversation(db, session_id, scope)
            messages = db.scalars(
                select(ConversationMessage)
                .where(ConversationMessage.session_id == session.id)
                .order_by(ConversationMessage.created_at.asc())
            ).all()
            result = self._conversation_to_dict(session)
            result["messages"] = [self._message_to_dict(message) for message in messages]
            return result

    def save_qa_exchange(
        self,
        session_id: str,
        question: str,
        answer: str,
        scope: dict[str, str],
        meta: dict | None = None,
    ) -> dict:
        with SessionLocal() as db:
            session = self._ensure_conversation(db, session_id, question, scope)
            user_created_at = datetime.now(timezone.utc)
            assistant_created_at = user_created_at + timedelta(microseconds=1)
            session.updated_at = assistant_created_at
            db.add(
                ConversationMessage(
                    id=self._new_id("msg"),
                    session_id=session.id,
                    role="user",
                    content=question,
                    meta_json="{}",
                    created_at=user_created_at,
                )
            )
            db.add(
                ConversationMessage(
                    id=self._new_id("msg"),
                    session_id=session.id,
                    role="assistant",
                    content=answer,
                    meta_json=json.dumps(meta or {}, ensure_ascii=False),
                    created_at=assistant_created_at,
                )
            )
            self._add_operation_log(
                db,
                scope,
                "qa.ask",
                "conversation",
                session.id,
                f"知识问答：{question.strip()[:80]}",
                {
                    "question_length": len(question),
                    "answer_length": len(answer),
                    "citation_count": len((meta or {}).get("citations", [])),
                    "trace_id": (meta or {}).get("trace_id"),
                },
            )
            db.commit()
            db.refresh(session)
            return self._conversation_to_dict(session)

    def _visible_documents_statement(self, scope: dict[str, str]):
        statement = (
            select(Document)
            .options(joinedload(Document.author), joinedload(Document.department))
            .where(Document.tenant_id == scope["tenant_id"])
        )
        if scope.get("role") != "admin":
            statement = statement.where(
                or_(
                    Document.visibility == "public",
                    Document.department_id == scope["department_id"],
                    Document.author_id == scope["user_id"],
                )
            )
        return statement

    def _get_visible_document(self, db, document_id: str, scope: dict[str, str]) -> Document:
        statement = self._visible_documents_statement(scope).where(Document.id == document_id)
        doc = db.scalar(statement)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在或无权访问")
        return doc

    def _get_owned_conversation(self, db, session_id: str, scope: dict[str, str]) -> ConversationSession:
        session = db.get(ConversationSession, session_id)
        if not session or session.tenant_id != scope["tenant_id"] or session.user_id != scope["user_id"]:
            raise HTTPException(status_code=404, detail="会话不存在或无权访问")
        return session

    def _ensure_conversation(self, db, session_id: str, question: str, scope: dict[str, str]) -> ConversationSession:
        session = db.get(ConversationSession, session_id)
        if session:
            if session.tenant_id != scope["tenant_id"] or session.user_id != scope["user_id"]:
                raise HTTPException(status_code=403, detail="无权写入该会话")
            return session

        title = question.strip().replace("\n", " ")[:80] or "新的知识问答"
        session = ConversationSession(
            id=session_id,
            tenant_id=scope["tenant_id"],
            user_id=scope["user_id"],
            title=title,
        )
        db.add(session)
        return session

    def _assert_can_edit(self, doc: Document, scope: dict[str, str]) -> None:
        if scope["role"] == "admin":
            return
        if doc.author_id == scope["user_id"]:
            return
        raise HTTPException(status_code=403, detail="无权编辑该文档")

    def _assert_admin(self, scope: dict[str, str]) -> None:
        if scope.get("role") != "admin":
            raise HTTPException(status_code=403, detail="仅管理员可访问管理后台")

    def _validate_status_filter(self, status: str | None, allowed: set[str], label: str) -> None:
        if status and status not in allowed:
            raise HTTPException(status_code=422, detail=f"{label}不支持")

    def _safe_limit(self, limit: int) -> int:
        return max(1, min(limit, 200))

    def _resolve_department_id(self, db, requested_department_id: str | None, scope: dict[str, str]) -> str:
        department_id = requested_department_id or scope["department_id"]
        department = db.get(Department, department_id)
        if not department or department.tenant_id != scope["tenant_id"]:
            raise HTTPException(status_code=400, detail="部门不存在")
        if scope["role"] != "admin" and department_id != scope["department_id"]:
            raise HTTPException(status_code=403, detail="无权写入其他部门")
        return department_id

    def _add_version(self, db, doc: Document, user_id: str, summary: str) -> None:
        db.add(
            DocumentVersion(
                id=self._new_id("ver"),
                document_id=doc.id,
                version=doc.version,
                title=doc.title,
                content=doc.content,
                summary=summary,
                created_by=user_id,
            )
        )

    def _add_operation_log(
        self,
        db,
        scope: dict[str, str],
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        summary: str = "",
        metadata: dict | None = None,
    ) -> OperationLog:
        log = OperationLog(
            id=self._new_id("log"),
            tenant_id=scope["tenant_id"],
            actor_id=scope.get("user_id") or scope.get("id"),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            summary=summary,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        db.add(log)
        return log

    def _scan_document_for_sensitive(
        self,
        db,
        doc: Document,
        scanner_id: str | None,
        trigger: str,
    ) -> SensitiveScan:
        findings = self._normalize_sensitive_findings(detect_sensitive_terms(doc.content))
        finding_count = len(findings)
        risk_level = self._sensitive_risk_level(findings)
        status = "needs_attention" if finding_count else "passed"
        suggestions = (
            ["发布前请删除或脱敏敏感字段", "必要时降低可见范围并补充审批说明"]
            if finding_count
            else ["未发现内置规则命中的敏感信息，可进入后续协作流程"]
        )
        summary = f"发现 {finding_count} 项敏感信息，建议处理后再发布" if finding_count else "未发现敏感信息"
        scan = SensitiveScan(
            id=self._new_id("scan"),
            tenant_id=doc.tenant_id,
            document_id=doc.id,
            scanner_id=scanner_id,
            status=status,
            risk_level=risk_level,
            finding_count=finding_count,
            findings_json=json.dumps(findings, ensure_ascii=False),
            summary=summary,
            suggestions_json=json.dumps(suggestions, ensure_ascii=False),
        )
        db.add(scan)
        db.flush()
        self._add_operation_log(
            db,
            {"tenant_id": doc.tenant_id, "user_id": scanner_id} if scanner_id else {"tenant_id": doc.tenant_id},
            "sensitive.scan",
            "document",
            doc.id,
            "执行敏感信息检测",
            {
                "scan_id": scan.id,
                "trigger": trigger,
                "risk_level": risk_level,
                "finding_count": finding_count,
            },
        )
        return scan

    def _normalize_sensitive_findings(self, findings: list[dict]) -> list[dict]:
        normalized = []
        for item in findings:
            rule_type = item.get("type", "keyword")
            term = item.get("term", "敏感信息")
            severity = "high" if rule_type == "pattern" else "medium"
            normalized.append(
                {
                    "type": "sensitive",
                    "rule_type": rule_type,
                    "severity": severity,
                    "term": term,
                    "sample": item.get("sample"),
                    "message": f"命中敏感信息规则：{term}",
                }
            )
        return normalized

    def _sensitive_risk_level(self, findings: list[dict]) -> str:
        if not findings:
            return "none"
        if any(item.get("severity") == "high" for item in findings):
            return "high"
        return "medium"

    def _document_to_dict(self, doc: Document) -> dict:
        latest_upload = doc.uploads[0] if doc.uploads else None
        latest_scan = doc.sensitive_scans[0] if doc.sensitive_scans else None
        return {
            "id": doc.id,
            "tenant_id": doc.tenant_id,
            "department_id": doc.department_id,
            "department": doc.department.name if doc.department else doc.department_id,
            "title": doc.title,
            "author": doc.author.name if doc.author else doc.author_id,
            "author_id": doc.author_id,
            "updated_at": doc.updated_at.isoformat(),
            "created_at": doc.created_at.isoformat(),
            "version": doc.version,
            "status": doc.status,
            "visibility": doc.visibility,
            "tags": json.loads(doc.tags_json or "[]"),
            "summary": doc.summary or self._summarize_document(doc.title, doc.content),
            "reads": doc.reads,
            "content": doc.content,
            "source_upload": self._upload_to_dict(latest_upload) if latest_upload else None,
            "sensitive_scan": self._sensitive_scan_to_dict(latest_scan) if latest_scan else None,
        }

    def _upload_to_dict(self, upload: DocumentUpload) -> dict:
        return {
            "id": upload.id,
            "document_id": upload.document_id,
            "original_filename": upload.original_filename,
            "stored_path": upload.stored_path,
            "content_type": upload.content_type,
            "size_bytes": upload.size_bytes,
            "parser": upload.parser,
            "status": upload.status,
            "error": upload.error,
            "created_at": upload.created_at.isoformat(),
        }

    def _sensitive_scan_to_dict(self, scan: SensitiveScan) -> dict:
        return {
            "id": scan.id,
            "tenant_id": scan.tenant_id,
            "document_id": scan.document_id,
            "document_title": scan.document.title if scan.document else scan.document_id,
            "scanner_id": scan.scanner_id,
            "scanner": scan.scanner.name if scan.scanner else None,
            "status": scan.status,
            "risk_level": scan.risk_level,
            "finding_count": scan.finding_count,
            "findings": self._json_or(scan.findings_json, []),
            "summary": scan.summary,
            "suggestions": self._json_or(scan.suggestions_json, []),
            "created_at": scan.created_at.isoformat(),
        }

    def _operation_log_to_dict(self, log: OperationLog) -> dict:
        return {
            "id": log.id,
            "tenant_id": log.tenant_id,
            "actor_id": log.actor_id,
            "actor": log.actor.name if log.actor else None,
            "actor_email": log.actor.email if log.actor else None,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "summary": log.summary,
            "metadata": self._json_or(log.metadata_json, {}),
            "created_at": log.created_at.isoformat(),
        }

    def _json_or(self, value: str | None, fallback):
        try:
            return json.loads(value or "")
        except json.JSONDecodeError:
            return fallback

    def _admin_user_to_dict(
        self,
        user: User,
        documents: list[Document],
        approvals: list[Approval],
        conversations: list[ConversationSession],
    ) -> dict:
        return {
            "id": user.id,
            "tenant_id": user.tenant_id,
            "department_id": user.department_id,
            "department": user.department.name if user.department else user.department_id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "created_at": user.created_at.isoformat(),
            "document_count": len([doc for doc in documents if doc.author_id == user.id]),
            "submitted_approval_count": len([approval for approval in approvals if approval.submitter_id == user.id]),
            "reviewed_approval_count": len([approval for approval in approvals if approval.reviewer_id == user.id]),
            "conversation_count": len([conversation for conversation in conversations if conversation.user_id == user.id]),
        }

    def _admin_department_to_dict(
        self,
        department: Department,
        users: list[User],
        documents: list[Document],
        approvals: list[Approval],
    ) -> dict:
        department_documents = [doc for doc in documents if doc.department_id == department.id]
        department_approvals = [
            approval
            for approval in approvals
            if approval.document and approval.document.department_id == department.id
        ]
        return {
            "id": department.id,
            "tenant_id": department.tenant_id,
            "name": department.name,
            "created_at": department.created_at.isoformat(),
            "user_count": len([user for user in users if user.department_id == department.id]),
            "document_count": len(department_documents),
            "published_count": len([doc for doc in department_documents if doc.status == "published"]),
            "pending_approval_count": len([approval for approval in department_approvals if approval.status == "pending"]),
            "upload_count": len([doc for doc in department_documents if doc.uploads]),
        }

    def _admin_upload_to_dict(self, upload: DocumentUpload) -> dict:
        row = self._upload_to_dict(upload)
        row.update(
            {
                "title": upload.document.title if upload.document else upload.document_id,
                "department": upload.department.name if upload.department else upload.department_id,
                "uploader": upload.uploader.name if upload.uploader else upload.uploader_id,
            }
        )
        return row

    def _document_status_counts(self, documents: list[Document]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for doc in documents:
            counts[doc.status] = counts.get(doc.status, 0) + 1
        return counts

    def _review_related_documents(self, db, doc: Document) -> list[dict]:
        rows = db.scalars(
            select(Document)
            .where(
                Document.tenant_id == doc.tenant_id,
                Document.id != doc.id,
                Document.status != "archived",
            )
            .order_by(Document.updated_at.desc())
            .limit(20)
        ).all()
        return [
            {
                "id": row.id,
                "title": row.title,
                "content": row.content,
                "status": row.status,
                "department_id": row.department_id,
            }
            for row in rows
        ]

    def _approval_to_dict(self, approval: Approval) -> dict:
        return {
            "id": approval.id,
            "document_id": approval.document_id,
            "title": approval.document.title if approval.document else approval.document_id,
            "submitter": approval.submitter.name if approval.submitter else approval.submitter_id,
            "submitted_at": approval.submitted_at.isoformat(),
            "status": approval.status,
            "summary": approval.summary,
            "agent_review": json.loads(approval.agent_review_json or "{}"),
            "reviewer": approval.reviewer.name if approval.reviewer else None,
            "reason": approval.reason,
            "reviewed_at": approval.reviewed_at.isoformat() if approval.reviewed_at else None,
        }

    def _version_to_dict(self, version: DocumentVersion) -> dict:
        return {
            "id": version.id,
            "document_id": version.document_id,
            "version": version.version,
            "title": version.title,
            "summary": version.summary,
            "created_by": version.creator.name if version.creator else version.created_by,
            "created_at": version.created_at.isoformat(),
        }

    def _comment_to_dict(self, comment: DocumentComment) -> dict:
        return {
            "id": comment.id,
            "document_id": comment.document_id,
            "author": comment.author.name if comment.author else comment.author_id,
            "author_id": comment.author_id,
            "content": comment.content,
            "created_at": comment.created_at.isoformat(),
        }

    def _conversation_to_dict(self, session: ConversationSession) -> dict:
        return {
            "id": session.id,
            "tenant_id": session.tenant_id,
            "user_id": session.user_id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        }

    def _message_to_dict(self, message: ConversationMessage) -> dict:
        return {
            "id": message.id,
            "session_id": message.session_id,
            "role": message.role,
            "content": message.content,
            "meta": json.loads(message.meta_json or "{}"),
            "created_at": message.created_at.isoformat(),
        }

    def _user_to_dict(self, user: User) -> dict:
        return {
            "id": user.id,
            "user_id": user.id,
            "tenant_id": user.tenant_id,
            "department_id": user.department_id,
            "department": user.department.name if user.department else user.department_id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
        }

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}-{uuid4().hex[:12]}"

    def _active_user_count(self, scope: dict[str, str]) -> int:
        with SessionLocal() as db:
            document_authors = db.scalars(
                select(Document.author_id).where(Document.tenant_id == scope["tenant_id"])
            ).all()
            conversation_users = db.scalars(
                select(ConversationSession.user_id).where(ConversationSession.tenant_id == scope["tenant_id"])
            ).all()
            return len(set(document_authors) | set(conversation_users))

    def _parse_datetime(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _is_since(self, value: datetime, since: datetime) -> bool:
        current = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        threshold = since.replace(tzinfo=timezone.utc) if since.tzinfo is None else since
        return current >= threshold

    def _summarize_document(self, title: str, content: str) -> str:
        clean = " ".join(content.split())
        if not clean:
            return f"{title}：暂无正文摘要"

        excerpt = clean
        for delimiter in ["。", "！", "？", ".", "!", "?"]:
            first_sentence = clean.split(delimiter, 1)[0].strip()
            if 20 <= len(first_sentence) <= 140:
                excerpt = f"{first_sentence}{delimiter}"
                break

        if len(excerpt) > 160:
            excerpt = f"{excerpt[:157].rstrip()}..."
        return f"{title}：{excerpt}"[:220]

    def _decode_uploaded_text(self, data: bytes) -> str:
        for encoding in ["utf-8-sig", "utf-8", "gb18030"]:
            try:
                content = data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise HTTPException(status_code=415, detail="文件编码无法解析，请上传 UTF-8 或 GB18030 文本")

        if not content.strip():
            raise HTTPException(status_code=400, detail="上传文件没有可解析正文")
        return content

    def _parse_upload_tags(self, tags: str) -> list[str]:
        if not tags:
            return []
        return [tag.strip() for tag in re.split(r"[,，]", tags) if tag.strip()]

    def _sanitize_filename(self, filename: str) -> str:
        normalized = filename.replace("\\", "/").split("/")[-1].strip()
        normalized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", normalized)
        if not normalized:
            return "upload.txt"
        if len(normalized) <= 240:
            return normalized

        suffix = Path(normalized).suffix
        stem = Path(normalized).stem[: max(1, 240 - len(suffix))]
        return f"{stem}{suffix}"

    def _store_upload_file(self, *, tenant_id: str, document_id: str, original_filename: str, data: bytes) -> str:
        root = self._upload_root()
        relative_dir = Path(tenant_id) / document_id
        target_dir = root / relative_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        stored_name = f"{uuid4().hex[:12]}-{original_filename}"
        target_path = target_dir / stored_name
        target_path.write_bytes(data)
        return (relative_dir / stored_name).as_posix()

    def _upload_root(self) -> Path:
        root = Path(settings.upload_dir)
        if root.is_absolute():
            return root
        return Path(__file__).resolve().parents[1] / root
