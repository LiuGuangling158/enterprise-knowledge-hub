import os
import shutil
import unittest
from pathlib import Path
from uuid import uuid4


TEST_DB = Path(__file__).resolve().parents[1] / "test_knowledge_v1.db"
TEST_UPLOAD_DIR = Path(__file__).resolve().parents[1] / "test-uploads"
if TEST_DB.exists():
    TEST_DB.unlink()
if TEST_UPLOAD_DIR.exists():
    shutil.rmtree(TEST_UPLOAD_DIR)

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["UPLOAD_DIR"] = str(TEST_UPLOAD_DIR)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from database.session import engine  # noqa: E402
from main import app  # noqa: E402


class V1FlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)
        engine.dispose()
        if TEST_DB.exists():
            TEST_DB.unlink()
        if TEST_UPLOAD_DIR.exists():
            shutil.rmtree(TEST_UPLOAD_DIR)

    def login(self, email: str) -> dict[str, str]:
        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": "123456"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_admin_backend_requires_admin_and_updates_user(self) -> None:
        admin_headers = self.login("admin@example.com")
        member_headers = self.login("product@example.com")

        blocked = self.client.get("/api/admin/overview", headers=member_headers)
        self.assertEqual(blocked.status_code, 403, blocked.text)

        suffix = uuid4().hex[:8]
        registered = self.client.post(
            "/api/auth/register",
            json={
                "name": f"后台测试用户{suffix}",
                "email": f"admin-flow-{suffix}@example.com",
                "password": "123456",
                "department_id": "dept-product",
            },
        )
        self.assertEqual(registered.status_code, 200, registered.text)
        user_id = registered.json()["user"]["id"]

        overview = self.client.get("/api/admin/overview", headers=admin_headers)
        self.assertEqual(overview.status_code, 200, overview.text)
        self.assertGreaterEqual(overview.json()["metrics"]["user_total"], 4)
        self.assertGreaterEqual(overview.json()["metrics"]["department_total"], 4)
        self.assertIn("department_breakdown", overview.json())

        departments = self.client.get("/api/admin/departments", headers=admin_headers)
        self.assertEqual(departments.status_code, 200, departments.text)
        self.assertIn("dept-tech", [row["id"] for row in departments.json()])

        updated = self.client.patch(
            f"/api/admin/users/{user_id}",
            headers=admin_headers,
            json={"role": "editor", "department_id": "dept-tech", "name": f"更新用户{suffix}"},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["role"], "editor")
        self.assertEqual(updated.json()["department_id"], "dept-tech")
        self.assertEqual(updated.json()["name"], f"更新用户{suffix}")

        users = self.client.get("/api/admin/users", headers=admin_headers)
        self.assertEqual(users.status_code, 200, users.text)
        updated_user = next(row for row in users.json() if row["id"] == user_id)
        self.assertEqual(updated_user["department"], "技术部")
        self.assertIn("document_count", updated_user)

        documents = self.client.get("/api/admin/documents", headers=admin_headers, params={"status": "reviewing"})
        self.assertEqual(documents.status_code, 200, documents.text)
        self.assertIn("doc-002", [row["id"] for row in documents.json()])

        approvals = self.client.get("/api/admin/approvals", headers=admin_headers, params={"status": "pending"})
        self.assertEqual(approvals.status_code, 200, approvals.text)
        self.assertIn("approval-001", [row["id"] for row in approvals.json()])

        invalid_status = self.client.get("/api/admin/documents", headers=admin_headers, params={"status": "deleted"})
        self.assertEqual(invalid_status.status_code, 422, invalid_status.text)

        blank_name = self.client.patch(
            f"/api/admin/users/{user_id}",
            headers=admin_headers,
            json={"name": "   "},
        )
        self.assertEqual(blank_name.status_code, 422, blank_name.text)

    def test_operation_logs_and_sensitive_scans_are_persisted(self) -> None:
        admin_headers = self.login("admin@example.com")
        member_headers = self.login("product@example.com")
        suffix = uuid4().hex[:8]

        created = self.client.post(
            "/api/documents",
            headers=member_headers,
            json={
                "title": f"敏感检测闭环 {suffix}",
                "content": "员工材料包含身份证、手机号 13812345678 和 api_key=secret-token-12345，需要检测。",
                "tags": ["敏感检测"],
                "visibility": "public",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        document_id = created.json()["id"]
        auto_scan = created.json()["sensitive_scan"]
        self.assertEqual(auto_scan["status"], "needs_attention")
        self.assertEqual(auto_scan["risk_level"], "high")
        self.assertGreaterEqual(auto_scan["finding_count"], 3)

        scans = self.client.get(f"/api/documents/{document_id}/sensitive-scans", headers=member_headers)
        self.assertEqual(scans.status_code, 200, scans.text)
        self.assertIn(auto_scan["id"], [row["id"] for row in scans.json()])

        manual_scan = self.client.post(f"/api/documents/{document_id}/sensitive-scan", headers=member_headers)
        self.assertEqual(manual_scan.status_code, 200, manual_scan.text)
        self.assertEqual(manual_scan.json()["risk_level"], "high")

        other_headers = self.login("tech@example.com")
        blocked_scan = self.client.post(f"/api/documents/{document_id}/sensitive-scan", headers=other_headers)
        self.assertEqual(blocked_scan.status_code, 403, blocked_scan.text)

        admin_scans = self.client.get(
            "/api/admin/sensitive-scans",
            headers=admin_headers,
            params={"risk_level": "high"},
        )
        self.assertEqual(admin_scans.status_code, 200, admin_scans.text)
        self.assertIn(document_id, [row["document_id"] for row in admin_scans.json()])

        blocked_admin_scans = self.client.get("/api/admin/sensitive-scans", headers=member_headers)
        self.assertEqual(blocked_admin_scans.status_code, 403, blocked_admin_scans.text)

        document_logs = self.client.get(
            "/api/admin/operation-logs",
            headers=admin_headers,
            params={"resource_type": "document"},
        )
        self.assertEqual(document_logs.status_code, 200, document_logs.text)
        related_actions = {
            row["action"]
            for row in document_logs.json()
            if row["resource_id"] == document_id
        }
        self.assertIn("document.create", related_actions)
        self.assertIn("sensitive.scan", related_actions)

        login_logs = self.client.get(
            "/api/admin/operation-logs",
            headers=admin_headers,
            params={"action": "auth.login"},
        )
        self.assertEqual(login_logs.status_code, 200, login_logs.text)
        self.assertTrue(any(row["actor_email"] == "admin@example.com" for row in login_logs.json()))

    def test_comment_and_document_approval_history_flow(self) -> None:
        headers = self.login("admin@example.com")
        suffix = uuid4().hex[:8]

        created = self.client.post(
            "/api/documents",
            headers=headers,
            json={
                "title": f"V1 flow doc {suffix}",
                "content": "Initial content",
                "tags": ["v1", "flow"],
                "visibility": "public",
                "department_id": "dept-product",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        document_id = created.json()["id"]
        self.assertIn("Initial content", created.json()["summary"])

        updated = self.client.put(
            f"/api/documents/{document_id}",
            headers=headers,
            json={
                "title": f"V1 flow doc {suffix}",
                "content": "Updated before submit",
                "tags": ["v1", "flow"],
                "visibility": "public",
                "summary": "Update before submit",
            },
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertIn("Updated before submit", updated.json()["summary"])

        compared = self.client.get(
            f"/api/documents/{document_id}/versions/compare",
            headers=headers,
            params={"left": 1, "right": 2},
        )
        self.assertEqual(compared.status_code, 200, compared.text)
        self.assertEqual(compared.json()["left_version"], 1)
        self.assertEqual(compared.json()["right_version"], 2)
        self.assertIn("-Initial content", compared.json()["diff"])
        self.assertIn("+Updated before submit", compared.json()["diff"])

        comment = self.client.post(
            f"/api/documents/{document_id}/comments",
            headers=headers,
            json={"content": "Looks ready for review."},
        )
        self.assertEqual(comment.status_code, 200, comment.text)
        self.assertEqual(comment.json()["content"], "Looks ready for review.")

        comments = self.client.get(f"/api/documents/{document_id}/comments", headers=headers)
        self.assertEqual(comments.status_code, 200, comments.text)
        self.assertEqual(len(comments.json()), 1)

        submitted = self.client.post(
            f"/api/documents/{document_id}/submit",
            headers=headers,
            json={"summary": "Submit for V1 approval"},
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        approval_id = submitted.json()["id"]
        self.assertIn("agent_review", submitted.json())
        self.assertEqual(submitted.json()["agent_review"]["agent"], "Review Agent")

        duplicate_submit = self.client.post(
            f"/api/documents/{document_id}/submit",
            headers=headers,
            json={"summary": "Duplicate V1 approval"},
        )
        self.assertEqual(duplicate_submit.status_code, 409, duplicate_submit.text)

        history = self.client.get(f"/api/documents/{document_id}/approvals", headers=headers)
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()[0]["id"], approval_id)
        self.assertEqual(history.json()[0]["status"], "pending")
        self.assertIn("summary", history.json()[0]["agent_review"])

        reviewed = self.client.post(
            f"/api/approvals/{approval_id}/review",
            headers=headers,
            json={"action": "approve", "reason": "Approved in V1 flow test"},
        )
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        self.assertEqual(reviewed.json()["status"], "approved")

        document = self.client.get(f"/api/documents/{document_id}", headers=headers)
        self.assertEqual(document.status_code, 200, document.text)
        self.assertEqual(document.json()["content"], "Updated before submit")
        self.assertEqual(document.json()["status"], "published")

    def test_non_admin_cannot_write_other_department_document(self) -> None:
        headers = self.login("product@example.com")
        response = self.client.post(
            "/api/documents",
            headers=headers,
            json={
                "title": "Cross department write",
                "content": "Should be blocked",
                "tags": [],
                "visibility": "department",
                "department_id": "dept-tech",
            },
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_text_upload_creates_document_and_source_record(self) -> None:
        headers = self.login("product@example.com")
        suffix = uuid4().hex[:8]
        filename = f"upload-flow-{suffix}.md"
        content = "# 上传闭环\n\n这是一份通过真实上传接口进入知识库的文档。"

        response = self.client.post(
            "/api/documents/upload",
            headers={**headers, "Content-Type": "text/markdown"},
            params={"filename": filename, "visibility": "department", "tags": "上传,测试"},
            content=content.encode("utf-8"),
        )
        self.assertEqual(response.status_code, 200, response.text)
        document = response.json()
        self.assertEqual(document["title"], f"upload-flow-{suffix}")
        self.assertEqual(document["content"], content)
        self.assertEqual(document["status"], "draft")
        self.assertEqual(document["tags"], ["上传", "测试"])
        self.assertIn("上传闭环", document["summary"])

        source_upload = document["source_upload"]
        self.assertEqual(source_upload["original_filename"], filename)
        self.assertEqual(source_upload["parser"], "markdown")
        self.assertEqual(source_upload["size_bytes"], len(content.encode("utf-8")))
        self.assertTrue((TEST_UPLOAD_DIR / source_upload["stored_path"]).exists())

        versions = self.client.get(f"/api/documents/{document['id']}/versions", headers=headers)
        self.assertEqual(versions.status_code, 200, versions.text)
        self.assertEqual(versions.json()[0]["summary"], f"上传解析：{filename}")

        search = self.client.get("/api/search", headers=headers, params={"q": "上传闭环"})
        self.assertEqual(search.status_code, 200, search.text)
        self.assertIn(document["id"], [item["document_id"] for item in search.json()["results"]])

        blocked = self.client.post(
            "/api/documents/upload",
            headers={**headers, "Content-Type": "text/plain"},
            params={"filename": "blocked.txt", "visibility": "department", "department_id": "dept-tech"},
            content="不能上传到其他部门".encode("utf-8"),
        )
        self.assertEqual(blocked.status_code, 403, blocked.text)

        unsupported = self.client.post(
            "/api/documents/upload",
            headers={**headers, "Content-Type": "application/pdf"},
            params={"filename": "blocked.pdf", "visibility": "department"},
            content=b"%PDF-1.7",
        )
        self.assertEqual(unsupported.status_code, 415, unsupported.text)

    def test_archive_hides_document_until_restored(self) -> None:
        headers = self.login("admin@example.com")
        suffix = uuid4().hex[:8]
        created = self.client.post(
            "/api/documents",
            headers=headers,
            json={
                "title": f"Archive flow doc {suffix}",
                "content": "Archive content",
                "tags": ["archive"],
                "visibility": "public",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        document_id = created.json()["id"]

        archived = self.client.post(f"/api/documents/{document_id}/archive", headers=headers)
        self.assertEqual(archived.status_code, 200, archived.text)
        self.assertEqual(archived.json()["status"], "archived")

        comment_archived = self.client.post(
            f"/api/documents/{document_id}/comments",
            headers=headers,
            json={"content": "Should be blocked"},
        )
        self.assertEqual(comment_archived.status_code, 409, comment_archived.text)

        default_documents = self.client.get("/api/documents", headers=headers)
        self.assertEqual(default_documents.status_code, 200, default_documents.text)
        self.assertNotIn(document_id, [item["id"] for item in default_documents.json()])

        archived_documents = self.client.get("/api/documents?status=archived", headers=headers)
        self.assertEqual(archived_documents.status_code, 200, archived_documents.text)
        self.assertIn(document_id, [item["id"] for item in archived_documents.json()])

        edit_archived = self.client.put(
            f"/api/documents/{document_id}",
            headers=headers,
            json={
                "title": "Should not edit archived",
                "content": "Blocked",
                "tags": ["archive"],
                "visibility": "public",
            },
        )
        self.assertEqual(edit_archived.status_code, 409, edit_archived.text)

        restored = self.client.post(f"/api/documents/{document_id}/restore", headers=headers)
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(restored.json()["status"], "draft")

        restored_documents = self.client.get("/api/documents", headers=headers)
        self.assertEqual(restored_documents.status_code, 200, restored_documents.text)
        self.assertIn(document_id, [item["id"] for item in restored_documents.json()])

    def test_non_author_cannot_archive_visible_document(self) -> None:
        headers = self.login("product@example.com")
        response = self.client.post("/api/documents/doc-002/archive", headers=headers)
        self.assertEqual(response.status_code, 403, response.text)

    def test_pending_approval_unique_index_exists(self) -> None:
        if engine.dialect.name != "sqlite":
            self.skipTest("index inspection is implemented for sqlite smoke tests")

        with engine.connect() as connection:
            rows = connection.execute(text("PRAGMA index_list('approvals')")).mappings().all()

        self.assertIn(
            "ix_approvals_one_pending_per_document",
            [row["name"] for row in rows],
        )

    def test_invalid_visibility_is_rejected(self) -> None:
        headers = self.login("admin@example.com")
        response = self.client.post(
            "/api/documents",
            headers=headers,
            json={
                "title": "Invalid visibility",
                "content": "Should be rejected",
                "tags": [],
                "visibility": "tenant",
            },
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_chunked_hybrid_search_returns_rrf_metadata(self) -> None:
        headers = self.login("admin@example.com")
        suffix = uuid4().hex[:8]
        content = "# 第一节\n" + ("流程说明" * 180) + f"\n# 第二节\n唯一检索信号 ABC{suffix} 用于验证分块召回。"
        created = self.client.post(
            "/api/documents",
            headers=headers,
            json={
                "title": f"RAG chunk doc {suffix}",
                "content": content,
                "tags": ["rag-upgrade"],
                "visibility": "public",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)

        search = self.client.get(
            "/api/search",
            headers=headers,
            params={"q": f"ABC{suffix}", "status": "draft", "tag": "rag-upgrade"},
        )
        self.assertEqual(search.status_code, 200, search.text)
        payload = search.json()
        self.assertEqual(payload["retrieval_meta"]["strategy"], "chunked_hybrid_rrf")
        self.assertGreaterEqual(payload["retrieval_meta"]["chunk_count"], 2)
        self.assertGreaterEqual(len(payload["results"]), 1)
        hit = payload["results"][0]
        self.assertIn("chunk-", hit["citation"])
        self.assertIn("chunk_id", hit)
        self.assertEqual(hit["retrieval_strategy"], "chunked_hybrid_rrf")
        self.assertIn("raw_scores", hit)
        self.assertIn("ABC", hit["snippet"])

    def test_submit_document_persists_agent_review_risks(self) -> None:
        headers = self.login("admin@example.com")
        suffix = uuid4().hex[:8]
        created = self.client.post(
            "/api/documents",
            headers=headers,
            json={
                "title": f"敏感审核文档 {suffix}",
                "content": "这是一份发布前审核文档，包含手机号 13812345678 和 api_key=secret-token-12345，需要 Agent 审核提示。",
                "tags": ["审核"],
                "visibility": "public",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)

        submitted = self.client.post(
            f"/api/documents/{created.json()['id']}/submit",
            headers=headers,
            json={"summary": "提交敏感信息审核"},
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        review = submitted.json()["agent_review"]
        self.assertEqual(review["status"], "needs_attention")
        self.assertEqual(review["risk_level"], "high")
        self.assertTrue(any(item["type"] == "sensitive" for item in review["findings"]))

        history = self.client.get(f"/api/documents/{created.json()['id']}/approvals", headers=headers)
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()[0]["agent_review"]["risk_level"], "high")

    def test_qa_conversation_history_is_persisted_per_user(self) -> None:
        headers = self.login("product@example.com")
        session_id = f"qa-test-{uuid4().hex[:8]}"
        question = "知识库检索架构如何携带引用来源？"

        response = self.client.post(
            "/api/ask",
            headers=headers,
            json={"question": question, "session_id": session_id},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("agent_plan", response.text)
        self.assertIn("tool_result", response.text)
        self.assertIn("guardrail_result", response.text)
        self.assertIn("output", response.text)
        self.assertIn(question, response.text)
        self.assertIn("conversation_saved", response.text)

        conversation = self.client.get(f"/api/conversations/{session_id}", headers=headers)
        self.assertEqual(conversation.status_code, 200, conversation.text)
        messages = conversation.json()["messages"]
        self.assertEqual([message["role"] for message in messages], ["user", "assistant"])
        self.assertEqual(messages[0]["content"], question)
        self.assertTrue(messages[1]["content"])
        self.assertIn("trace_id", messages[1]["meta"])
        self.assertIn("agent_trace", messages[1]["meta"])
        self.assertEqual(messages[1]["meta"]["retrieval_meta"]["strategy"], "chunked_hybrid_rrf")
        self.assertGreaterEqual(len(messages[1]["meta"]["agent_trace"]), 4)
        self.assertEqual(messages[1]["meta"]["run_summary"]["question"], question)
        trace_outputs = [
            item.get("output", "")
            for item in messages[1]["meta"]["agent_trace"]
            if isinstance(item, dict)
        ]
        self.assertTrue(any(question[:8] in output for output in trace_outputs))
        citations = messages[1]["meta"]["citations"]
        self.assertGreaterEqual(len(citations), 1)
        self.assertIn("document_id", citations[0])
        self.assertIn("version", citations[0])
        self.assertIn("snippet", citations[0])
        self.assertIn("source", citations[0])
        self.assertEqual(citations[0]["source"]["citation"], citations[0]["citation"])

        search = self.client.get("/api/search", headers=headers, params={"q": "检索架构"})
        self.assertEqual(search.status_code, 200, search.text)
        self.assertIn("source", search.json()["results"][0])
        self.assertIn("retrieval_meta", search.json())
        self.assertEqual(search.json()["results"][0]["retrieval_strategy"], "chunked_hybrid_rrf")

        capabilities = self.client.get("/api/agents/capabilities", headers=headers)
        self.assertEqual(capabilities.status_code, 200, capabilities.text)
        self.assertEqual(["router", "retrieval", "qa", "memory"], [item["id"] for item in capabilities.json()["agents"]])

        other_user_headers = self.login("tech@example.com")
        blocked = self.client.get(f"/api/conversations/{session_id}", headers=other_user_headers)
        self.assertEqual(blocked.status_code, 404, blocked.text)


if __name__ == "__main__":
    unittest.main()
