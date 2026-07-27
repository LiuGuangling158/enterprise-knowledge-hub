import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from core.config import settings
from core.security import hash_password, verify_password
from database.models import Approval, Department, Document, DocumentComment, DocumentVersion, User
from database.session import SessionLocal


class DocumentService:
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
            db.commit()
            db.refresh(user)
            return self._user_to_dict(user)

    def authenticate_user(self, email: str, password: str) -> dict | None:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == email))
            if not user or not verify_password(password, user.password_hash):
                return None
            return self._user_to_dict(user)

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
                author_id=scope["user_id"],
                status="draft",
                visibility=payload.visibility,
                version=1,
                tags_json=json.dumps(payload.tags, ensure_ascii=False),
            )
            db.add(doc)
            db.flush()
            self._add_version(db, doc, scope["user_id"], "创建文档")
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
            for field in ["title", "content", "visibility"]:
                value = getattr(payload, field)
                if value is not None and getattr(doc, field) != value:
                    setattr(doc, field, value)
                    changed = True
            if payload.department_id is not None:
                department_id = self._resolve_department_id(db, payload.department_id, scope)
                if doc.department_id != department_id:
                    doc.department_id = department_id
                    changed = True
            if payload.tags is not None:
                doc.tags_json = json.dumps(payload.tags, ensure_ascii=False)
                changed = True

            if changed:
                doc.version += 1
                doc.status = "draft"
                doc.updated_at = datetime.now(timezone.utc)
                self._add_version(db, doc, scope["user_id"], payload.summary or "保存文档")
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

            doc.status = "reviewing"
            doc.updated_at = datetime.now(timezone.utc)
            approval = Approval(
                id=self._new_id("approval"),
                document_id=doc.id,
                submitter_id=scope["user_id"],
                status="pending",
                summary=payload.summary,
            )
            db.add(approval)
            db.commit()
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
            self._get_visible_document(db, document_id, scope)
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
            db.commit()
            db.refresh(comment)
            return self._comment_to_dict(comment)

    def metrics(self, scope: dict[str, str]) -> dict:
        rows = self.list_documents(scope)
        since = datetime.now(timezone.utc) - timedelta(days=7)
        weekly_new = len([row for row in rows if self._parse_datetime(row["created_at"]) >= since])
        pending = len([item for item in self.list_approvals(scope) if item["status"] == "pending"])
        return {
            "document_total": len(rows),
            "weekly_new": weekly_new,
            "active_users": 128,
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

    def all_visible_text(self, scope: dict[str, str]) -> list[dict]:
        return self.list_documents(scope)

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

    def _assert_can_edit(self, doc: Document, scope: dict[str, str]) -> None:
        if scope["role"] == "admin":
            return
        if doc.author_id == scope["user_id"]:
            return
        raise HTTPException(status_code=403, detail="无权编辑该文档")

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

    def _document_to_dict(self, doc: Document) -> dict:
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
            "reads": doc.reads,
            "content": doc.content,
        }

    def _approval_to_dict(self, approval: Approval) -> dict:
        return {
            "id": approval.id,
            "document_id": approval.document_id,
            "title": approval.document.title if approval.document else approval.document_id,
            "submitter": approval.submitter.name if approval.submitter else approval.submitter_id,
            "submitted_at": approval.submitted_at.isoformat(),
            "status": approval.status,
            "summary": approval.summary,
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

    def _parse_datetime(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
