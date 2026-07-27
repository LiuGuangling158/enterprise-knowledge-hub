from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from core.security import hash_password
from database.models import Approval, Department, Document, DocumentVersion, Tenant, User


def seed_demo_data(db: Session) -> None:
    existing = db.scalar(select(User).where(User.email == "admin@example.com"))
    if existing:
        return

    tenant = Tenant(id=settings.demo_tenant_id, name="示例企业")
    departments = [
        Department(id="dept-product", tenant_id=tenant.id, name="产品部"),
        Department(id="dept-tech", tenant_id=tenant.id, name="技术部"),
        Department(id="dept-hr", tenant_id=tenant.id, name="人事部"),
        Department(id="dept-finance", tenant_id=tenant.id, name="财务部"),
    ]
    users = [
        User(
            id="user-admin",
            tenant_id=tenant.id,
            department_id="dept-product",
            email="admin@example.com",
            name="秦川",
            role="admin",
            password_hash=hash_password("123456"),
        ),
        User(
            id="user-product",
            tenant_id=tenant.id,
            department_id="dept-product",
            email="product@example.com",
            name="林知远",
            role="editor",
            password_hash=hash_password("123456"),
        ),
        User(
            id="user-tech",
            tenant_id=tenant.id,
            department_id="dept-tech",
            email="tech@example.com",
            name="周明",
            role="editor",
            password_hash=hash_password("123456"),
        ),
    ]
    documents = [
        Document(
            id="doc-001",
            tenant_id=tenant.id,
            department_id="dept-product",
            title="产品需求评审流程",
            content="需求进入评审前，产品经理需要完成背景、目标、范围、验收标准和风险说明。评审通过后提交到发布审批中心。",
            author_id="user-product",
            status="published",
            visibility="department",
            version=4,
            tags_json='["产品","流程","审批"]',
            reads=186,
        ),
        Document(
            id="doc-002",
            tenant_id=tenant.id,
            department_id="dept-tech",
            title="知识库检索架构设计",
            content="检索链路采用 Query 改写、语义召回、关键词召回、元数据过滤和 RRF 融合重排序。回答必须携带引用来源。",
            author_id="user-tech",
            status="reviewing",
            visibility="public",
            version=2,
            tags_json='["技术","RAG","架构"]',
            reads=142,
        ),
        Document(
            id="doc-003",
            tenant_id=tenant.id,
            department_id="dept-hr",
            title="新员工入职手册",
            content="新员工入职第一周需要完成账号开通、部门导师确认、制度培训和知识库阅读清单确认。",
            author_id="user-admin",
            status="published",
            visibility="public",
            version=7,
            tags_json='["人事","培训","制度"]',
            reads=321,
        ),
    ]
    versions = [
        DocumentVersion(
            id="ver-001",
            document_id="doc-001",
            version=4,
            title="产品需求评审流程",
            content=documents[0].content,
            summary="补充验收标准说明。",
            created_by="user-product",
        ),
        DocumentVersion(
            id="ver-002",
            document_id="doc-002",
            version=2,
            title="知识库检索架构设计",
            content=documents[1].content,
            summary="新增多路召回和引用溯源章节。",
            created_by="user-tech",
        ),
    ]
    approvals = [
        Approval(
            id="approval-001",
            document_id="doc-002",
            submitter_id="user-tech",
            status="pending",
            summary="新增多路召回和引用溯源章节，补充 RRF 重排序说明。",
        ),
        Approval(
            id="approval-002",
            document_id="doc-001",
            submitter_id="user-product",
            reviewer_id="user-admin",
            status="approved",
            summary="补充验收标准模板。",
        ),
    ]

    db.add(tenant)
    db.add_all(departments)
    db.add_all(users)
    db.add_all(documents)
    db.add_all(versions)
    db.add_all(approvals)
    db.commit()
